import csv
import io
import re
from collections import Counter
from datetime import date
from decimal import Decimal

MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 10_000
AMOUNT_PATTERN = r"([0-9]+|[0-9]{1,3}(,[0-9]{3})+)(\.[0-9]{1,2})?"
DATE_PATTERN = r"[0-9]{4}-[0-9]{2}-[0-9]{2}"
WHITESPACE = " \t\r\n"
COLUMNS = ("order_id", "order_date", "amount")
AMOUNT_MAX = Decimal("9999999999.99")
PREVIEW_SIZE = 12
ERROR_LIMIT = 100


class InputError(ValueError):
    pass


def batch_month(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}", value):
        raise InputError("Choose a valid batch month.")
    try:
        return date.fromisoformat(value + "-01")
    except ValueError as exc:
        raise InputError("Choose a valid batch month.") from exc


def extract(source):
    try:
        reader = csv.reader(io.StringIO(source.decode("utf-8-sig"), newline=""), strict=True)
        header = tuple(cell.strip(WHITESPACE).lower() for cell in next(reader, ()))
        if len(header) != len(COLUMNS) or set(header) != set(COLUMNS):
            raise InputError("Use exactly these CSV columns: order_id, order_date, amount.")
        indices = [header.index(column) for column in COLUMNS]
        start, rows = reader.line_num + 1, []
        for fields in reader:
            position, start = start, reader.line_num + 1
            if not fields:
                continue
            if len(fields) != len(COLUMNS):
                raise InputError(f"Row {position} must have exactly three fields.")
            if any(len(field) > 256 or "\x00" in field for field in fields):
                raise InputError(f"Row {position} contains an invalid or oversized field.")
            rows.append((position, *(fields[index] for index in indices)))
            if len(rows) > MAX_ROWS:
                raise InputError(f"An orders file may contain at most {MAX_ROWS:,} data rows.")
    except (UnicodeError, csv.Error) as exc:
        raise InputError("The file is not a valid UTF-8 CSV.") from exc
    if not rows:
        raise InputError("The CSV needs at least one data row.")
    return rows


def transform(rows, month):
    ids = Counter(row[1].strip(WHITESPACE) for row in rows)
    clean, errors = [], []
    for row_no, order_id, order_date, amount in rows:
        order_id = order_id.strip(WHITESPACE)
        order_date = order_date.strip(WHITESPACE)
        amount = amount.strip(WHITESPACE).removeprefix("₱").strip(WHITESPACE)
        try:
            parsed_date = date.fromisoformat(order_date) if re.fullmatch(DATE_PATTERN, order_date) else None
        except ValueError:
            parsed_date = None
        parsed_amount = Decimal(amount.replace(",", "")) if re.fullmatch(AMOUNT_PATTERN, amount) else None
        if not order_id:
            issue = "Order ID is required."
        elif ids[order_id] > 1:
            issue = "Duplicate order ID."
        elif parsed_date is None:
            issue = "Use a valid date in YYYY-MM-DD format."
        elif parsed_date.replace(day=1) != month:
            issue = "Order date is outside the batch month."
        elif parsed_amount is None or parsed_amount > AMOUNT_MAX:
            issue = "Enter a non-negative amount with up to two decimal places."
        else:
            clean.append((row_no, order_id, parsed_date.isoformat(), format(parsed_amount, ".2f")))
            continue
        errors.append({"row": row_no, "message": issue})
    return clean, errors
