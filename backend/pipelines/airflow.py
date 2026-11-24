import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from django.conf import settings

from . import runs
from .orders import MAX_ROWS, extract
from .warehouse import insert_orders

DAG_PATH = "/api/v2/dags/autumnleaf_orders/dagRuns"
STATES = {"queued", "running", "success", "failed"}


class AirflowUnavailable(Exception):
    pass


class RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def available():
    url = urlsplit(settings.AIRFLOW_URL)
    return bool(
        url.scheme == "http"
        and url.hostname in {"localhost", "127.0.0.1", "::1"}
        and not (url.username or url.password or url.query or url.fragment or url.path.rstrip("/"))
        and settings.AIRFLOW_USER
        and settings.AIRFLOW_PASSWORD
    )


def request(path, data=None, token=None, allow_existing=False):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = Request(settings.AIRFLOW_URL.rstrip("/") + path,
                  json.dumps(data).encode() if data is not None else None, headers)
    try:
        with build_opener(ProxyHandler({}), RejectRedirects()).open(req, timeout=4) as response:
            return json.load(response)
    except HTTPError as exc:
        if allow_existing and exc.code == 409:
            return {}
        raise AirflowUnavailable("Airflow did not accept the request. Check that its local service and orders workflow are ready.") from exc
    except (URLError, TimeoutError, ValueError) as exc:
        raise AirflowUnavailable("Could not reach the local Airflow service.") from exc


def access_token():
    if not available():
        raise AirflowUnavailable("The local Airflow connection is not configured.")
    result = request("/auth/token", {"username": settings.AIRFLOW_USER, "password": settings.AIRFLOW_PASSWORD})
    token = result.get("access_token") if isinstance(result, dict) else None
    if not isinstance(token, str) or not token:
        raise AirflowUnavailable("Airflow did not return an access token.")
    return token


def start(run_id):
    request(DAG_PATH, {"dag_run_id": str(run_id), "logical_date": None, "conf": {"job_id": str(run_id)}},
            token=access_token(), allow_existing=True)


def state(run_id):
    result = request(f"{DAG_PATH}/{run_id}", token=access_token())
    value = result.get("state") if isinstance(result, dict) else None
    if value not in STATES:
        raise AirflowUnavailable("Airflow did not report a recognized run state.")
    return value


def job_path(run_id):
    return Path(settings.AIRFLOW_JOB_ROOT) / str(run_id)


def prepare(directory, run):
    path = job_path(run["id"])
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    manifest = path / "job.json"
    if not manifest.exists():
        source = runs.source_path(directory, run["id"]).read_bytes()
        (path / "source.csv").write_bytes(source)
        manifest.write_text(json.dumps({
            "month": run["month"].isoformat()[:7], "checksum": run["checksum"],
        }), encoding="utf-8")


def complete(db, directory, run, state):
    run_id = run["id"]
    if state not in {"success", "failed"}:
        db.execute(
            "UPDATE orchestrations SET state = ? WHERE run_id = ? AND NOT (state = 'running' AND ? = 'queued')",
            [state, run_id, state],
        )
        return

    try:
        with (job_path(run_id) / "result.json").open(encoding="utf-8") as result_file:
            outcome = json.loads(result_file.read(12 * 1024 * 1024 + 1))
        if not isinstance(outcome, dict) or outcome.get("checksum") != run["checksum"]:
            raise ValueError("Invalid candidate receipt.")
        if outcome.get("loaded") is True:
            source = runs.source_path(directory, run_id).read_bytes()
            if hashlib.sha256(source).hexdigest() != run["checksum"]:
                raise ValueError("The source file has changed.")
            raw = extract(source)
        else:
            raw = []
        errors = outcome.get("errors", [])
        clean = outcome.get("clean")
        if not isinstance(errors, list) or len(errors) > MAX_ROWS:
            raise ValueError("Invalid candidate errors.")
        if state == "success" and (
            not isinstance(clean, list) or not raw or len(clean) != len(raw)
            or any(not isinstance(row, list) or len(row) != 4 or row[0] != original[0] for row, original in zip(clean, raw))
        ):
            raise ValueError("Invalid candidate rows.")
    except (OSError, ValueError):
        runs.fail(db, run_id, "Airflow did not produce a usable result. Check the local task logs.")
        db.execute("UPDATE orchestrations SET state = 'failed' WHERE run_id = ?", [run_id])
        return

    if raw:
        insert_orders(db, "raw", run_id, raw)
        db.execute("UPDATE runs SET step = 2, source_count = ? WHERE id = ?", [len(raw), run_id])
    if state == "failed":
        runs.fail(db, run_id, outcome.get("message") or "The automated pipeline failed.", errors,
                  len(raw) - len(errors) if errors else None)
    else:
        insert_orders(db, "staging", run_id, clean)
        runs.finish(db, run)
    db.execute("UPDATE orchestrations SET state = ? WHERE run_id = ?", [state, run_id])
