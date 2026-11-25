from datetime import date
from io import BytesIO

from django.http import FileResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell

from identity.views import body, error, signed_in
from pipelines.orders import MAX_ROWS, InputError, batch_month
from pipelines.warehouse import warehouse

QUERY_LIMIT = 30
SQL_LIMIT = 8000
QUERY_SCHEMA = """
CREATE TABLE IF NOT EXISTS worksheet_queries (
    name VARCHAR PRIMARY KEY,
    sql VARCHAR NOT NULL
)
"""


def selection(request):
    mode = request.GET.get("mode")
    if mode not in {"etl", "elt"}:
        raise InputError("Choose ETL or ELT.")
    return batch_month(request.GET.get("month")), mode


def report_period(request, month):
    try:
        start, end = (
            date.fromisoformat(value) if value else None
            for value in (request.GET.get("from"), request.GET.get("to"))
        )
    except ValueError as exc:
        raise InputError("Choose valid report dates.") from exc
    if any(value and value.replace(day=1) != month for value in (start, end)):
        raise InputError("Report dates must be in the selected batch month.")
    if start and end and start > end:
        raise InputError("The start date must be on or before the end date.")
    return start, end


def published(account, month, mode, include_orders=False, period=(None, None)):
    with warehouse(account) as (db, _):
        selected = db.execute(
            "SELECT run_id FROM mart.batches WHERE month = ? AND mode = ?", [month, mode]
        ).fetchone()
        if not selected:
            return None, [], []
        batch = selected[0]
        start, end = period
        daily = db.execute(
            """SELECT order_date, order_count, revenue FROM mart.daily_sales
               WHERE month = ? AND mode = ? AND order_date >= coalesce(?, order_date)
               AND order_date <= coalesce(?, order_date) ORDER BY order_date""",
            [month, mode, start, end],
        ).fetchall()
        orders = db.execute(
            """SELECT order_id, order_date, amount FROM staging.orders
               WHERE run_id = ? ORDER BY order_date, order_id LIMIT ?""",
            [batch, MAX_ROWS + 1],
        ).fetchall() if include_orders else []
    if len(orders) > MAX_ROWS:
        raise InputError("The selected batch is too large for a browser snapshot.")
    return str(batch), daily, orders


def summary(month, mode, batch, daily):
    return {
        "month": month.strftime("%Y-%m"),
        "mode": mode,
        "batch": batch,
        "daily": daily,
        "order_count": sum(row[1] for row in daily),
        "revenue": format(sum((row[2] for row in daily), 0), ".2f"),
    }


@never_cache
@require_GET
@signed_in
def snapshot(request, account):
    try:
        month, mode = selection(request)
        batch, daily, orders = published(account, month, mode, include_orders=True)
    except InputError as exc:
        return error(str(exc))
    return JsonResponse({**summary(month, mode, batch, daily), "orders": orders})


@never_cache
@require_GET
@signed_in
def report(request, account):
    try:
        month, mode = selection(request)
        batch, daily, _ = published(account, month, mode, period=report_period(request, month))
    except InputError as exc:
        return error(str(exc))
    return JsonResponse(summary(month, mode, batch, daily))


@never_cache
@require_GET
@signed_in
def export(request, account):
    try:
        month, mode = selection(request)
        start, end = report_period(request, month)
        batch, daily, _ = published(account, month, mode, period=(start, end))
    except InputError as exc:
        return error(str(exc))
    if not batch:
        return error("No published batch exists for this month and mode.", 404)
    if request.GET.get("batch") != batch:
        return error("The published batch changed. Refresh the report before downloading.", 409)

    book = Workbook(write_only=True)
    overview = book.create_sheet("Summary")
    sales = book.create_sheet("Daily sales")
    totals = summary(month, mode, batch, daily)
    revenue = WriteOnlyCell(overview, value=sum((row[2] for row in daily), 0))
    revenue.number_format = '#,##0.00'
    for row in [
        ("Batch month", totals["month"]), ("Mode", mode.upper()), ("Batch ID", batch),
        ("From", start or "Start of batch"), ("To", end or "End of batch"),
        ("Orders", totals["order_count"]), ("Revenue", revenue),
    ]:
        overview.append(row)
    sales.append(("Order date", "Orders", "Revenue"))
    for when, count, amount in daily:
        money = WriteOnlyCell(sales, value=amount)
        money.number_format = '#,##0.00'
        sales.append((when, count, money))
    content = BytesIO()
    book.save(content)
    content.seek(0)
    return FileResponse(content, as_attachment=True, filename=f"sales-{month:%Y-%m}-{mode}.xlsx")


@never_cache
@require_http_methods(["GET", "POST"])
@signed_in
def queries(request, account):
    if request.method == "POST":
        value = body(request)
        name = value.get("name")
        sql = value.get("sql")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 64:
            return error("Enter a query name up to 64 characters.")
        if not isinstance(sql, str) or not sql.strip() or len(sql) > SQL_LIMIT:
            return error(f"Enter a query up to {SQL_LIMIT:,} characters.")
        name = name.strip()

    with warehouse(account) as (db, _):
        db.execute(QUERY_SCHEMA)
        if request.method == "POST":
            count = db.execute("SELECT count(*) FROM worksheet_queries WHERE name <> ?", [name]).fetchone()[0]
            if count >= QUERY_LIMIT:
                return error("You have 30 saved queries. Reuse an existing name to replace it.", 400)
            db.execute(
                "INSERT INTO worksheet_queries VALUES (?, ?) ON CONFLICT (name) DO UPDATE SET sql = excluded.sql",
                [name, sql],
            )
        results = db.execute("SELECT name, sql FROM worksheet_queries ORDER BY lower(name), name").fetchall()
    return JsonResponse({"queries": [{"name": name, "sql": sql} for name, sql in results]})
