import hashlib
import json
import uuid
from pathlib import Path

from .orders import AMOUNT_PATTERN, DATE_PATTERN, ERROR_LIMIT, PREVIEW_SIZE, extract, transform
from .warehouse import insert_orders, record

TRANSFORM_SQL = Path(__file__).with_name("transform.sql").read_text(encoding="utf-8")
STEPS = {"etl": ("Extract", "Transform", "Load"), "elt": ("Extract", "Load", "Transform")}


def get_run(db, run_id):
    return record(db, "SELECT * FROM runs WHERE id = ?", [run_id])


def automation(db, run_id):
    return record(db, "SELECT state FROM orchestrations WHERE run_id = ?", [run_id])


def history(db):
    result = db.execute("SELECT * FROM runs ORDER BY created_at DESC, id LIMIT 30")
    columns = [column[0] for column in result.description]
    return [summary(dict(zip(columns, row))) for row in result.fetchall()]


def current_run(db, mode, month):
    return record(db, """SELECT r.* FROM mart.batches b JOIN runs r ON b.run_id = r.id
                         WHERE b.mode = ? AND b.month = ?""", [mode, month])


def source_path(directory, run_id):
    return directory / f"{run_id}.csv"


def clean_path(directory, run_id):
    return directory / f"{run_id}.clean.json"


def summary(run):
    if not run:
        return None
    return {
        **{key: run[key] for key in (
            "id", "mode", "filename", "checksum", "status", "step", "source_count",
            "row_count", "revenue", "error", "error_count", "created_at", "finalized_at",
        )},
        "month": run["month"].isoformat()[:7],
    }


def detail(db, directory, run):
    run_id, completed = run["id"], run["step"]
    data = {
        **summary(run),
        "errors": json.loads(run["errors"]),
        "source_preview": extract(source_path(directory, run_id).read_bytes())[:PREVIEW_SIZE] if completed else [],
        "clean_preview": [],
        "replacement": None,
        "automation": automation(db, run_id),
    }
    if run["mode"] == "etl" and completed == 2:
        data["clean_preview"] = json.loads(clean_path(directory, run_id).read_text(encoding="utf-8"))[:PREVIEW_SIZE]
    if completed == 3:
        data["clean_preview"] = db.execute(
            """SELECT row_no, order_id, order_date, amount FROM staging.orders
               WHERE run_id = ? ORDER BY row_no LIMIT ?""", [run_id, PREVIEW_SIZE]
        ).fetchall()
    if run["status"] == "review":
        data["replacement"] = summary(get_run(db, run["baseline"]))
    return data


def upload(db, directory, mode, month, filename, source):
    checksum = hashlib.sha256(source).hexdigest()
    current = current_run(db, mode, month)
    if current and current["checksum"] == checksum:
        return current, True
    existing = record(db, """SELECT * FROM runs WHERE mode = ? AND month = ? AND checksum = ?
                             AND status IN ('in_progress', 'review')
                             ORDER BY created_at DESC LIMIT 1""", [mode, month, checksum])
    if existing:
        return existing, False

    run_id = uuid.uuid4()
    source_path(directory, run_id).write_bytes(source)
    return record(
        db,
        """INSERT INTO runs (id, mode, month, filename, checksum) VALUES (?, ?, ?, ?, ?)
           RETURNING *""",
        [run_id, mode, month, filename, checksum],
    ), False


def fail(db, run_id, reason, errors=(), valid_rows=None):
    db.execute(
        """UPDATE runs SET status = 'failed', error = ?, error_count = ?, errors = ?,
           row_count = ?, finalized_at = now() WHERE id = ?""",
        [reason, len(errors), json.dumps(errors[:ERROR_LIMIT]), valid_rows, run_id],
    )


def publish(db, run):
    db.execute(
        """INSERT INTO mart.batches VALUES (?, ?, ?)
           ON CONFLICT (mode, month) DO UPDATE SET run_id = excluded.run_id""",
        [run["mode"], run["month"], run["id"]],
    )
    db.execute("UPDATE runs SET status = 'published', finalized_at = now() WHERE id = ?", [run["id"]])


def finish(db, run):
    run_id = run["id"]
    count, revenue = db.execute(
        "SELECT count(*), sum(amount) FROM staging.orders WHERE run_id = ?", [run_id]
    ).fetchone()
    db.execute("UPDATE runs SET step = 3, row_count = ?, revenue = ? WHERE id = ?", [count, revenue, run_id])
    current = current_run(db, run["mode"], run["month"])
    if not current:
        publish(db, run)
    elif current["checksum"] == run["checksum"]:
        db.execute("UPDATE runs SET status = 'unchanged', finalized_at = now() WHERE id = ?", [run_id])
    else:
        db.execute("UPDATE runs SET status = 'review', baseline = ? WHERE id = ?", [current["id"], run_id])


def advance(db, directory, run):
    run_id, completed, mode = run["id"], run["step"], run["mode"]
    if completed == 0:
        rows = extract(source_path(directory, run_id).read_bytes())
        db.execute("UPDATE runs SET step = 1, source_count = ? WHERE id = ?", [len(rows), run_id])
        return
    if completed == 1:
        rows = extract(source_path(directory, run_id).read_bytes())
        if mode == "etl":
            clean, errors = transform(rows, run["month"])
            if errors:
                fail(db, run_id, "Some rows failed validation. No batch was published.", errors, len(clean))
                return
            clean_path(directory, run_id).write_text(json.dumps(clean, ensure_ascii=False), encoding="utf-8")
            db.execute("UPDATE runs SET row_count = ? WHERE id = ?", [len(clean), run_id])
        else:
            insert_orders(db, "raw", run_id, rows)
        db.execute("UPDATE runs SET step = 2 WHERE id = ?", [run_id])
        return

    if mode == "etl":
        clean = json.loads(clean_path(directory, run_id).read_text(encoding="utf-8"))
        insert_orders(db, "staging", run_id, clean)
    else:
        db.execute("CREATE TEMP TABLE checked_orders AS " + TRANSFORM_SQL, {
            "run_id": run_id, "month": run["month"], "date_pattern": DATE_PATTERN, "amount_pattern": AMOUNT_PATTERN,
        })
        errors = [
            {"row": row_no, "message": issue}
            for row_no, issue in db.execute(
                "SELECT row_no, issue FROM checked_orders WHERE issue IS NOT NULL ORDER BY row_no"
            ).fetchall()
        ]
        if errors:
            fail(db, run_id, "Some rows failed validation. Raw rows are available for inspection.", errors, run["source_count"] - len(errors))
            return
        db.execute(
            "INSERT INTO staging.orders SELECT ?, row_no, order_id, order_date, amount FROM checked_orders",
            [run_id],
        )
    finish(db, run)


def approve_replacement(db, run, baseline):
    current = current_run(db, run["mode"], run["month"])
    if not current:
        return False
    if current["id"] != run["baseline"] or str(current["id"]) != baseline:
        db.execute("UPDATE runs SET baseline = ? WHERE id = ?", [current["id"], run["id"]])
        return False
    if current["checksum"] == run["checksum"]:
        db.execute("UPDATE runs SET status = 'unchanged', finalized_at = now() WHERE id = ?", [run["id"]])
    else:
        publish(db, run)
    return True


def compare(db, month):
    etl, elt = (current_run(db, mode, month) for mode in STEPS)
    result = {"etl": summary(etl), "elt": summary(elt), "matches": None, "different_orders": None}
    if etl and elt:
        count = db.execute(
            """WITH e AS (SELECT order_id, order_date, amount FROM staging.orders WHERE run_id = ?),
                    l AS (SELECT order_id, order_date, amount FROM staging.orders WHERE run_id = ?)
               SELECT count(*) FROM e FULL JOIN l USING (order_id)
               WHERE e.order_date IS DISTINCT FROM l.order_date OR e.amount IS DISTINCT FROM l.amount""",
            [etl["id"], elt["id"]],
        ).fetchone()[0]
        result.update(matches=count == 0, different_orders=count)
    return result
