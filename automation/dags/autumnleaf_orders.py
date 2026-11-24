import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from airflow.sdk import dag, get_current_context, task

RUNNER = Path(__file__).resolve().parents[1] / "runner.py"


def run_candidate(action):
    job_id = str(UUID(get_current_context()["dag_run"].conf["job_id"]))
    subprocess.run([os.environ["AUTUMNLEAF_DBT_PYTHON"], RUNNER, action, job_id], check=True, timeout=150)


@dag(dag_id="autumnleaf_orders", schedule=None, start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
     catchup=False, max_active_runs=1, tags=["autumnleaf", "elt"])
def orders():
    @task
    def load_raw():
        run_candidate("load")

    @task
    def dbt_build():
        run_candidate("build")

    @task
    def prepare_candidate():
        run_candidate("export")

    load_raw() >> dbt_build() >> prepare_candidate()


orders()
