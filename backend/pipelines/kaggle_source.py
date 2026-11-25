import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tempfile import TemporaryDirectory

from .orders import AMOUNT_MAX, COLUMNS, MAX_BYTES, MAX_ROWS, InputError


class KaggleUnavailable(Exception):
    pass


@dataclass(frozen=True)
class Dataset:
    handle: str
    file: str
    title: str
    sample_month: str
    columns: tuple[str, str, str]
    date_format: str = "%Y-%m-%d"
    encoding: str = "utf-8-sig"
    status: str = ""


DATASETS = {
    "retail-sales": Dataset(
        "mohammadtalib786/retail-sales-dataset/versions/1",
        "retail_sales_dataset.csv", "Retail Sales", "2023-02",
        ("Transaction ID", "Date", "Total Amount"),
    ),
    "sample-sales": Dataset(
        "kyanyoga/sample-sales-data/versions/1",
        "sales_data_sample.csv", "Sample Sales · Shipped orders", "2004-11",
        ("ORDERNUMBER", "ORDERDATE", "SALES"), "%m/%d/%Y %H:%M", "cp1252", "Shipped",
    ),
}


def download(dataset):
    try:
        from kagglehub import dataset_download
    except ImportError as exc:
        raise KaggleUnavailable("Kaggle support is not installed on this AutumnLeaf server.") from exc

    # The user never supplies a host, dataset path, version or archive name.
    # Delete the original file as soon as its bounded contents have been read.
    try:
        with TemporaryDirectory(prefix="autumnleaf-kaggle-") as directory:
            path = dataset_download(dataset.handle, path=dataset.file, output_dir=directory)
            with Path(path).open("rb") as source:
                data = source.read(MAX_BYTES + 1)
    except Exception as exc:
        raise KaggleUnavailable("Kaggle could not supply the selected file. Try again later.") from exc
    if len(data) > MAX_BYTES:
        raise InputError("The Kaggle CSV is larger than 2 MiB.")
    return data


def prepare(dataset, raw, month):
    reader = csv.DictReader(io.StringIO(raw.decode(dataset.encoding), newline=""), strict=True)
    order_col, date_col, amount_col = dataset.columns
    required = set(dataset.columns) | ({"STATUS"} if dataset.status else set())
    if not required.issubset(reader.fieldnames or ()):
        raise InputError("The selected dataset no longer has the expected columns.")

    orders = {}
    for index, row in enumerate(reader, 1):
        if index > MAX_ROWS:
            raise InputError(f"The Kaggle CSV exceeds {MAX_ROWS:,} rows.")
        if None in row or any(row[column] is None for column in required):
            raise InputError("The Kaggle CSV has a row with missing or extra fields.")
        if dataset.status and row["STATUS"] != dataset.status:
            continue
        ordered = datetime.strptime(row[date_col], dataset.date_format).date()
        if ordered.replace(day=1) != month:
            continue
        order_id = row[order_col].strip()
        amount = Decimal(row[amount_col])
        if not order_id or len(order_id) > 256 or "\x00" in order_id or not amount.is_finite() or not 0 <= amount <= AMOUNT_MAX:
            raise InputError("A Kaggle order has an invalid ID or amount.")
        if order_id in orders:
            first_date, first_amount = orders[order_id]
            if not dataset.status or ordered != first_date:
                raise InputError("The Kaggle CSV has conflicting order IDs.")
            amount += first_amount
        orders[order_id] = (ordered, amount)

    if not orders:
        raise InputError("This dataset has no eligible orders in the selected month.")

    rows = []
    for order_id, (ordered, amount) in sorted(orders.items()):
        if amount > AMOUNT_MAX or amount != amount.quantize(Decimal("0.01")):
            raise InputError("A Kaggle order total does not fit the orders amount format.")
        rows.append((order_id, date.isoformat(ordered), format(amount, ".2f")))
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\n").writerows([COLUMNS, *rows])
    return output.getvalue().encode("utf-8"), rows


def prepare_batch(dataset, month):
    try:
        return prepare(dataset, download(dataset), month)
    except InputError:
        raise
    except (ValueError, InvalidOperation, csv.Error) as exc:
        raise InputError("The Kaggle CSV has a date, amount, or format AutumnLeaf cannot read.") from exc
