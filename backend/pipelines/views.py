from pathlib import Path

from django.http import FileResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from identity.views import body, error, signed_in

from . import airflow, runs
from .orders import MAX_BYTES, InputError, batch_month
from .warehouse import TABLES, preview, transaction, warehouse

SAMPLE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "orders"
SAMPLES = {"november.csv", "november-corrected.csv", "november-invalid.csv"}


@never_cache
@require_GET
@signed_in
def pipeline_sample(request, account, filename):
    if filename not in SAMPLES:
        return error("Sample CSV not found.", 404)
    return FileResponse((SAMPLE_DIR / filename).open("rb"), as_attachment=True, filename=filename)


@never_cache
@require_http_methods(["GET", "POST"])
@signed_in
def pipeline_runs(request, account):
    if request.method == "GET":
        with warehouse(account) as (db, _):
            return JsonResponse({"runs": runs.history(db), "automation_available": airflow.available()})

    file = request.FILES.get("file")
    mode = request.POST.get("mode")
    if mode not in runs.STEPS:
        return error("Choose ETL or ELT.")
    try:
        month = batch_month(request.POST.get("month"))
    except InputError as exc:
        return error(str(exc))
    if not file or not file.name.lower().endswith(".csv"):
        return error("Upload an orders CSV file.")
    source = file.read(MAX_BYTES + 1)
    if len(source) > MAX_BYTES:
        return error("CSV files must be no larger than 2 MiB.", 413)

    with warehouse(account) as (db, directory), transaction(db):
        run, reused = runs.upload(db, directory, mode, month, file.name, source)
        return JsonResponse({"run": runs.detail(db, directory, run), "reused": reused}, status=200 if reused else 201)


@never_cache
@require_GET
@signed_in
def pipeline_detail(request, account, run_id):
    with warehouse(account) as (db, directory):
        run = runs.get_run(db, run_id)
        if not run:
            return error("Pipeline run not found.", 404)
        return JsonResponse({"run": runs.detail(db, directory, run)})


@never_cache
@require_POST
@signed_in
def pipeline_advance(request, account, run_id):
    expected = body(request).get("step") if request.content_type == "application/json" else None
    with warehouse(account) as (db, directory), transaction(db):
        run = runs.get_run(db, run_id)
        if not run:
            return error("Pipeline run not found.", 404)
        if type(expected) is not int or run["step"] != expected or run["status"] != "in_progress" or runs.automation(db, run_id):
            return error("This run has changed. Open its current step and try again.", 409)
        try:
            runs.advance(db, directory, run)
        except InputError as exc:
            runs.fail(db, run_id, str(exc))
        return JsonResponse({"run": runs.detail(db, directory, runs.get_run(db, run_id))})


@never_cache
@require_POST
@signed_in
def pipeline_automate(request, account, run_id):
    with warehouse(account) as (db, directory):
        run = runs.get_run(db, run_id)
        if not run:
            return error("Pipeline run not found.", 404)
        if runs.automation(db, run_id):
            return JsonResponse({"run": runs.detail(db, directory, run)})
        if run["mode"] != "elt" or run["step"] != 0 or run["status"] != "in_progress":
            return error("Start an unprocessed ELT upload before handing it to Airflow.", 409)
        if not airflow.available():
            return error("The local Airflow connection is not configured.", 503)
        airflow.prepare(directory, run)

    try:
        airflow.start(run_id)
    except airflow.AirflowUnavailable as exc:
        return error(str(exc), 503)

    with warehouse(account) as (db, directory), transaction(db):
        run = runs.get_run(db, run_id)
        if not runs.automation(db, run_id):
            if run["step"] != 0 or run["status"] != "in_progress":
                return error("This run was already started manually. The Airflow candidate will not publish.", 409)
            db.execute("INSERT INTO orchestrations VALUES (?, 'queued')", [run_id])
        return JsonResponse({"run": runs.detail(db, directory, run)})


@never_cache
@require_POST
@signed_in
def pipeline_sync(request, account, run_id):
    with warehouse(account) as (db, directory):
        run = runs.get_run(db, run_id)
        if not run or not runs.automation(db, run_id):
            return error("Automated pipeline run not found.", 404)
        if run["status"] != "in_progress":
            return JsonResponse({"run": runs.detail(db, directory, run)})

    try:
        state = airflow.state(run_id)
    except airflow.AirflowUnavailable as exc:
        return error(str(exc), 503)

    with warehouse(account) as (db, directory), transaction(db):
        run = runs.get_run(db, run_id)
        if run["status"] == "in_progress":
            airflow.complete(db, directory, run, state)
        return JsonResponse({"run": runs.detail(db, directory, runs.get_run(db, run_id))})


@never_cache
@require_POST
@signed_in
def pipeline_publish(request, account, run_id):
    baseline = body(request).get("baseline") if request.content_type == "application/json" else None
    if not isinstance(baseline, str):
        return error("Review the current batch before replacing it.")
    with warehouse(account) as (db, directory), transaction(db):
        run = runs.get_run(db, run_id)
        if not run:
            return error("Pipeline run not found.", 404)
        if run["status"] != "review":
            return error("This run is not waiting for replacement approval.", 409)
        if not runs.approve_replacement(db, run, baseline):
            return error("The published batch changed. Review the updated comparison before replacing it.", 409)
        return JsonResponse({"run": runs.detail(db, directory, runs.get_run(db, run_id))})


@never_cache
@require_GET
@signed_in
def pipeline_compare(request, account):
    try:
        month = batch_month(request.GET.get("month"))
    except InputError as exc:
        return error(str(exc))
    with warehouse(account) as (db, _):
        return JsonResponse(runs.compare(db, month))


@never_cache
@require_GET
@signed_in
def warehouse_tables(request, account):
    name = request.GET.get("table", "mart.daily_sales")
    try:
        offset = int(request.GET.get("offset", 0))
    except ValueError:
        return error("Choose a valid page.")
    if name not in TABLES or offset < 0 or offset > 1_000_000:
        return error("Choose a valid table and page.")
    with warehouse(account) as (db, _):
        return JsonResponse({"tables": list(TABLES), "table": name, **preview(db, name, offset)})
