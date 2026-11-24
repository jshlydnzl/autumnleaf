from contextlib import contextmanager
from pathlib import Path
from threading import Lock

import duckdb
from django.conf import settings

from .orders import COLUMNS

# Native DuckDB is owned by one app process; bound that process to one request at a time.
WAREHOUSE_LOCK = Lock()

SCHEMA = """
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS mart;
CREATE TABLE IF NOT EXISTS runs (
    id UUID PRIMARY KEY,
    mode VARCHAR NOT NULL,
    month DATE NOT NULL,
    filename VARCHAR NOT NULL,
    checksum VARCHAR NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'in_progress',
    step INTEGER NOT NULL DEFAULT 0,
    source_count INTEGER,
    row_count INTEGER,
    revenue DECIMAL(18, 2),
    error VARCHAR,
    error_count INTEGER NOT NULL DEFAULT 0,
    errors JSON NOT NULL DEFAULT '[]',
    baseline UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finalized_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS orchestrations (run_id UUID PRIMARY KEY, state VARCHAR NOT NULL);
CREATE TABLE IF NOT EXISTS raw.orders (
    run_id UUID NOT NULL, row_no INTEGER NOT NULL,
    order_id VARCHAR NOT NULL, order_date VARCHAR NOT NULL, amount VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS staging.orders (
    run_id UUID NOT NULL, row_no INTEGER NOT NULL,
    order_id VARCHAR NOT NULL, order_date DATE NOT NULL, amount DECIMAL(12, 2) NOT NULL
);
CREATE TABLE IF NOT EXISTS mart.batches (
    mode VARCHAR NOT NULL, month DATE NOT NULL, run_id UUID NOT NULL,
    PRIMARY KEY (mode, month)
);
CREATE VIEW IF NOT EXISTS mart.daily_sales AS
    SELECT b.mode, b.month, s.order_date, count(*) AS order_count, sum(s.amount) AS revenue
    FROM staging.orders s JOIN mart.batches b USING (run_id)
    GROUP BY b.mode, b.month, s.order_date;
"""

TABLES = {
    "raw.orders": ("run_id", "row_no", *COLUMNS),
    "staging.orders": ("run_id", "row_no", *COLUMNS),
    "mart.daily_sales": ("mode", "month", "order_date", "order_count", "revenue"),
}


@contextmanager
def warehouse(account):
    with WAREHOUSE_LOCK:
        directory = Path(settings.WAREHOUSE_ROOT) / str(account.pk)
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        db = duckdb.connect(
            str(directory / "orders.duckdb"), config={"enable_external_access": "false", "threads": "2"}
        )
        try:
            db.execute(SCHEMA)
            yield db, directory
        finally:
            db.close()


@contextmanager
def transaction(db):
    db.execute("BEGIN")
    try:
        yield
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise


def record(db, query, params=()):
    result = db.execute(query, params)
    row = result.fetchone()
    return dict(zip((column[0] for column in result.description), row)) if row else None


def insert_orders(db, table, run_id, rows):
    numbers, ids, dates, amounts = zip(*rows)
    target = "raw.orders" if table == "raw" else "staging.orders"
    date_type, amount_type = ("VARCHAR", "VARCHAR") if table == "raw" else ("DATE", "DECIMAL(12, 2)")
    db.execute(
        f"""INSERT INTO {target}
            SELECT ?::UUID, unnest(?::INTEGER[]), unnest(?::VARCHAR[]),
                   unnest(?::{date_type}[]), unnest(?::{amount_type}[])""",
        [run_id, list(numbers), list(ids), list(dates), list(amounts)],
    )


def preview(db, name, offset=0):
    columns = TABLES[name]
    count = db.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
    rows = db.execute(
        f"SELECT * FROM {name} ORDER BY {', '.join(columns[:2])}, {columns[2]} LIMIT 25 OFFSET ?", [offset]
    ).fetchall()
    types = [str(column[1]) for column in db.description]
    return {"columns": list(map(list, zip(columns, types))), "rows": rows, "total": count}
