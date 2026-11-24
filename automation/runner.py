"""Run local pipeline tasks against a candidate database, never the live warehouse."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from pipelines.orders import AMOUNT_PATTERN, DATE_PATTERN, InputError, batch_month, extract

PROJECT = Path(__file__).with_name("dbt")


def write_result(directory, payload):
    pending = directory / "result.pending"
    pending.write_text(json.dumps(payload, default=str), encoding="utf-8")
    pending.replace(directory / "result.json")


def load(directory, source, receipt):
    try:
        rows = extract(source)
    except InputError as exc:
        write_result(directory, {**receipt, "loaded": False, "message": str(exc)})
        raise SystemExit(1) from None
    with duckdb.connect(str(directory / "candidate.duckdb"), config={"threads": "2"}) as db:
        db.execute("CREATE SCHEMA IF NOT EXISTS raw")
        db.execute("CREATE OR REPLACE TABLE raw.orders (row_no INTEGER, order_id VARCHAR, order_date VARCHAR, amount VARCHAR)")
        db.execute(
            "INSERT INTO raw.orders SELECT unnest(?::INTEGER[]), unnest(?::VARCHAR[]), unnest(?::VARCHAR[]), unnest(?::VARCHAR[])",
            [list(column) for column in zip(*rows)],
        )


def build(directory, month, receipt):
    result = subprocess.run(
        [Path(sys.executable).with_name("dbt"), "build", "--project-dir", PROJECT,
         "--profiles-dir", PROJECT, "--target-path", directory / "target",
         "--log-path", directory / "logs", "--vars", json.dumps({
             "batch_month": month.isoformat(), "date_pattern": DATE_PATTERN, "amount_pattern": AMOUNT_PATTERN,
         })],
        env={**os.environ, "AUTUMNLEAF_CANDIDATE_DB": str(directory / "candidate.duckdb"),
             "DBT_SEND_ANONYMOUS_USAGE_STATS": "false"},
        check=False,
        timeout=120,
    )
    if result.returncode == 0:
        return
    errors = []
    with duckdb.connect(str(directory / "candidate.duckdb"), read_only=True, config={"threads": "2"}) as db:
        if db.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='main' AND table_name='checked_orders'").fetchone()[0]:
            errors = [
                {"row": row_no, "message": issue}
                for row_no, issue in db.execute(
                    "SELECT row_no, issue FROM main.checked_orders WHERE issue IS NOT NULL ORDER BY row_no"
                ).fetchall()
            ]
    write_result(directory, {
        **receipt, "loaded": True, "errors": errors,
        "message": "dbt rejected invalid orders." if errors else "The dbt build did not pass. Check its Airflow task log.",
    })
    raise SystemExit(1)


def export(directory, receipt):
    with duckdb.connect(str(directory / "candidate.duckdb"), read_only=True, config={"threads": "2"}) as db:
        rows = db.execute("SELECT row_no, order_id, order_date, amount FROM main.stg_orders ORDER BY row_no").fetchall()
    write_result(directory, {**receipt, "loaded": True, "clean": rows})


def main(action, job_id):
    directory = Path(os.environ["AUTUMNLEAF_JOB_ROOT"]) / str(UUID(job_id))
    manifest = json.loads((directory / "job.json").read_text(encoding="utf-8"))
    month = batch_month(manifest["month"])
    source = (directory / "source.csv").read_bytes()
    checksum = hashlib.sha256(source).hexdigest()
    if checksum != manifest["checksum"]:
        raise ValueError("The source checksum does not match the run.")
    receipt = {"checksum": checksum}
    if action == "load":
        load(directory, source, receipt)
    elif action == "build":
        build(directory, month, receipt)
    elif action == "export":
        export(directory, receipt)
    else:
        raise ValueError("Unrecognized pipeline task.")


if __name__ == "__main__":
    main(*sys.argv[1:])
