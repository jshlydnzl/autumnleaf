from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from openpyxl import load_workbook

from identity.models import Account

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "orders"
SELECTION = {"month": "2026-11", "mode": "elt"}
PASSWORD = "Sample-Worksheet-934!"


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class WorkbenchTests(TestCase):
    def setUp(self):
        store = TemporaryDirectory()
        self.addCleanup(store.cleanup)
        self.enterContext(override_settings(WAREHOUSE_ROOT=Path(store.name)))
        self.owner = self.sign_in("owner")
        self.other = self.sign_in("other")

    def sign_in(self, username):
        Account.objects.create(user=get_user_model().objects.create_user(username=username, password=PASSWORD))
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(self.post(client, "/api/auth/login/", {"username": username, "password": PASSWORD}).status_code, 200)
        return client

    def post(self, client, path, data, as_json=True):
        token = client.get("/api/auth/csrf/").json()["csrfToken"]
        options = {"content_type": "application/json"} if as_json else {}
        return client.post(path, data, HTTP_X_CSRFTOKEN=token, **options)

    def publish_fixture(self, name):
        data = {
            **SELECTION, "file": SimpleUploadedFile(name, (FIXTURES / name).read_bytes()),
        }
        run = self.post(self.owner, "/api/pipelines/", data, as_json=False).json()["run"]
        for step in range(3):
            run = self.post(self.owner, f"/api/pipelines/{run['id']}/advance/", {"step": step}).json()["run"]
        return run

    def test_snapshot_report_and_workbook_match_for_published_batch(self):
        self.assertEqual(Client().get("/api/analysis/snapshot/", SELECTION).status_code, 401)
        self.assertIsNone(self.owner.get("/api/analysis/report/", SELECTION).json()["batch"])
        self.assertEqual(self.owner.get("/api/analysis/report/", {**SELECTION, "mode": "other"}).status_code, 400)
        run = self.publish_fixture("november.csv")
        snapshot = self.owner.get("/api/analysis/snapshot/", SELECTION).json()
        report = self.owner.get("/api/analysis/report/", SELECTION).json()
        self.assertEqual({key: value for key, value in snapshot.items() if key != "orders"}, report)
        self.assertEqual((report["batch"], report["order_count"], report["revenue"]), (run["id"], 2, "2000.00"))
        self.assertEqual(len(snapshot["orders"]), 2)
        self.assertEqual(self.other.get("/api/analysis/snapshot/", SELECTION).json()["orders"], [])
        self.assertEqual(self.other.get("/api/analysis/export/", {**SELECTION, "batch": run["id"]}).status_code, 404)

        response = self.owner.get("/api/analysis/export/", {**SELECTION, "batch": report["batch"]})
        self.assertEqual(response.status_code, 200)
        self.assertIn("sales-2026-11-elt.xlsx", response["Content-Disposition"])
        book = load_workbook(BytesIO(b"".join(response.streaming_content)), read_only=True)
        self.addCleanup(book.close)
        summary = dict(book["Summary"].values)
        self.assertEqual(summary["Batch ID"], run["id"])
        self.assertEqual((summary["Orders"], summary["Revenue"]), (2, 2000))
        self.assertEqual(sum(row[2] for row in list(book["Daily sales"].values)[1:]), 2000)

        selected_days = {**SELECTION, "from": "2026-11-17", "to": "2026-11-18"}
        filtered = self.owner.get("/api/analysis/report/", selected_days).json()
        self.assertEqual((filtered["order_count"], filtered["revenue"]), (1, "750.00"))
        exported = self.owner.get("/api/analysis/export/", {**selected_days, "batch": run["id"]})
        with BytesIO(b"".join(exported.streaming_content)) as contents:
            filtered_book = load_workbook(contents, read_only=True)
            self.assertEqual(dict(filtered_book["Summary"].values)["Revenue"], 750)
            filtered_book.close()
        self.assertEqual(self.owner.get("/api/analysis/report/", {**selected_days, "to": "2026-10-31"}).status_code, 400)

        replacement = self.publish_fixture("november-corrected.csv")
        self.assertEqual(replacement["status"], "review")
        self.post(self.owner, f"/api/pipelines/{replacement['id']}/publish/", {"baseline": run["id"]})
        self.assertEqual(self.owner.get("/api/analysis/report/", SELECTION).json()["revenue"], "1300.00")
        self.assertEqual(self.owner.get("/api/analysis/export/", {**SELECTION, "batch": run["id"]}).status_code, 409)

    def test_saved_queries_are_account_scoped_and_only_store_text(self):
        url = "/api/analysis/queries/"
        self.assertEqual(self.owner.post(url, {}, content_type="application/json").status_code, 403)
        self.assertEqual(self.post(self.owner, url, {"name": "", "sql": "SELECT 1"}).status_code, 400)
        sql = "SELECT SUM(revenue) FROM mart.daily_sales"
        self.assertEqual(self.post(self.owner, url, {"name": " Totals ", "sql": sql}).json()["queries"], [{"name": "Totals", "sql": sql}])
        self.assertEqual(self.other.get(url).json()["queries"], [])
        self.assertIsNone(self.owner.get("/api/analysis/report/", SELECTION).json()["batch"])
