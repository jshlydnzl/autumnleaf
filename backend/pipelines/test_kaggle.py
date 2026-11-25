from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from identity.models import Account

from .kaggle_source import KaggleUnavailable

IMPORT = "/api/pipelines/kaggle/import/"
RETAIL = b"Transaction ID,Date,Total Amount,Customer ID\n123,2023-02-03,16.50,DO-NOT-IMPORT\n124,2023-03-04,4.00,OTHER-MONTH\n"
SALES = b"ORDERNUMBER,ORDERDATE,SALES,STATUS\n21,11/5/2004 0:00,5.10,Shipped\n21,11/5/2004 0:00,0.02,Shipped\n21,11/5/2004 0:00,9.12,Cancelled\n"


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class KagglePipelineTests(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.enterContext(override_settings(WAREHOUSE_ROOT=Path(temp.name)))
        self.client = self.sign_in("buyer")

    def sign_in(self, username):
        user = get_user_model().objects.create_user(username=username, password="Synthetic-Leaf-5610")
        Account.objects.create(user=user, role=Account.Role.MEMBER)
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(self.post(client, "/api/auth/login/", {
            "username": username, "password": "Synthetic-Leaf-5610",
        }).status_code, 200)
        return client

    def post(self, client, url, payload):
        token = client.get("/api/auth/csrf/").json()["csrfToken"]
        return client.post(url, payload, content_type="application/json", HTTP_X_CSRFTOKEN=token)

    def test_import_flows_through_existing_elt_and_respects_account_boundaries(self):
        base = {"dataset": "retail-sales", "month": "2023-02"}
        self.assertEqual(self.client.get("/api/pipelines/kaggle/catalog/").json()["categories"][0]["id"], "commerce")
        self.assertEqual(Client().get("/api/pipelines/kaggle/catalog/").status_code, 401)
        self.assertEqual(Client().post(IMPORT, base, content_type="application/json").status_code, 401)
        self.assertEqual(self.client.post(IMPORT, base, content_type="application/json").status_code, 403)
        self.assertEqual(self.post(self.client, IMPORT, {**base, "dataset": "https://example.invalid"}).status_code, 404)
        with patch("pipelines.kaggle_source.download", return_value=RETAIL):
            preview = self.post(self.client, IMPORT, base).json()
            self.assertEqual(preview["rows"], [["123", "2023-02-03", "16.50"]])
            self.assertEqual(preview["total"], 1)
            self.assertEqual(self.client.get("/api/pipelines/").json()["runs"], [])
            changed = self.post(self.client, IMPORT, {**base, "mode": "elt", "checksum": "outdated"})
            self.assertEqual(changed.status_code, 409)
            payload = {**base, "mode": "elt", "checksum": preview["checksum"]}
            response = self.post(self.client, IMPORT, payload)
            self.assertEqual(response.status_code, 201, response.content)
            run = response.json()["run"]
            self.assertEqual(run["filename"], "kaggle-retail-sales-2023-02.csv")
            self.assertEqual(self.sign_in("reader").get(f"/api/pipelines/{run['id']}/").status_code, 404)
            for step in range(3):
                run = self.post(self.client, f"/api/pipelines/{run['id']}/advance/", {"step": step}).json()["run"]
            self.assertEqual((run["status"], run["revenue"]), ("published", "16.50"))
            self.assertTrue(self.post(self.client, IMPORT, payload).json()["reused"])

    def test_orders_are_grouped_and_only_shipped_lines_count(self):
        with patch("pipelines.kaggle_source.download", return_value=SALES):
            response = self.post(self.client, IMPORT, {"dataset": "sample-sales", "month": "2004-11"})
        self.assertEqual(response.json()["rows"], [["21", "2004-11-05", "5.12"]])

    def test_missing_month_provider_failure_and_schema_drift_do_not_create_runs(self):
        payload = {"dataset": "retail-sales", "month": "2023-04"}
        for data in (RETAIL, b"wrong,header\n1,2\n"):
            with patch("pipelines.kaggle_source.download", return_value=data):
                self.assertEqual(self.post(self.client, IMPORT, payload).status_code, 400)
        with patch("pipelines.kaggle_source.download", side_effect=KaggleUnavailable("Unavailable")):
            self.assertEqual(self.post(self.client, IMPORT, payload).status_code, 503)
        self.assertEqual(self.client.get("/api/pipelines/").json()["runs"], [])
