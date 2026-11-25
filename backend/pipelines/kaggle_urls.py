from hashlib import sha256

from django.http import JsonResponse
from django.urls import path
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from identity.views import body, error, signed_in

from . import kaggle_source, runs
from .orders import MAX_BYTES, PREVIEW_SIZE, InputError, batch_month
from .warehouse import transaction, warehouse


@never_cache
@require_GET
@signed_in
def catalog(request, account):
    return JsonResponse({"categories": [{
        "id": "commerce",
        "title": "E-commerce & retail",
        "datasets": [
            {"id": key, "title": item.title, "sample_month": item.sample_month,
             "url": f"https://www.kaggle.com/datasets/{item.handle.rsplit('/versions/', 1)[0]}"}
            for key, item in kaggle_source.DATASETS.items()
        ],
    }]})


@never_cache
@require_POST
@signed_in
def import_orders(request, account):
    value = body(request)
    key = value.get("dataset")
    dataset = kaggle_source.DATASETS.get(key) if isinstance(key, str) else None
    if not dataset:
        return error("Choose a dataset from the Kaggle catalog.", 404)
    mode = value.get("mode")
    checksum = value.get("checksum")
    if checksum is not None and (not isinstance(mode, str) or mode not in runs.STEPS or not isinstance(checksum, str)):
        return error("Choose ETL or ELT and preview the dataset first.")
    try:
        month = batch_month(value.get("month"))
        source, rows = kaggle_source.prepare_batch(dataset, month)
    except InputError as exc:
        return error(str(exc))
    except kaggle_source.KaggleUnavailable as exc:
        return error(str(exc), 503)
    if len(source) > MAX_BYTES:
        return error("The prepared CSV is larger than 2 MiB.", 413)
    fingerprint = sha256(source).hexdigest()
    if checksum is None:
        return JsonResponse({"checksum": fingerprint, "rows": rows[:PREVIEW_SIZE], "total": len(rows)})
    if checksum != fingerprint:
        return error("The source changed. Preview it again before starting a run.", 409)

    with warehouse(account) as (db, directory), transaction(db):
        filename = f"kaggle-{key}-{month:%Y-%m}.csv"
        run, reused = runs.upload(db, directory, mode, month, filename, source)
        return JsonResponse({"run": runs.detail(db, directory, run), "reused": reused}, status=200 if reused else 201)


urlpatterns = [
    path("pipelines/kaggle/catalog/", catalog),
    path("pipelines/kaggle/import/", import_orders),
]
