from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from identity.models import Account

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "orders"
PASSWORD = "Synthetic-Leaf-5610"


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PipelineTests(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.enterContext(override_settings(WAREHOUSE_ROOT=Path(temp.name)))
        user_model = get_user_model()
        for name, role in (("owner", "admin"), ("member", "member")):
            user = user_model.objects.create_user(username=name, password=PASSWORD)
            Account.objects.create(user=user, role=role)
        self.client = self.session("owner", csrf=True)

    def session(self, name, csrf=False):
        client = Client(enforce_csrf_checks=csrf)
        self.send(client, "/api/auth/login/", {"username": name, "password": PASSWORD}, content_type="application/json")
        self.assertEqual(client.get("/api/auth/session/").status_code, 200)
        return client

    def send(self, client, path, data, **kwargs):
        token = client.get("/api/auth/csrf/").json()["csrfToken"]
        return client.post(path, data, HTTP_X_CSRFTOKEN=token, **kwargs)

    def upload(self, mode, fixture="november.csv", month="2026-11", content=None):
        response = self.send(self.client, "/api/pipelines/", {
            "mode": mode,
            "month": month,
            "file": SimpleUploadedFile(fixture, (FIXTURES / fixture).read_bytes() if content is None else content),
        })
        self.assertIn(response.status_code, (200, 201), response.content)
        return response.json()

    def action(self, run, action, data):
        return self.send(self.client, f"/api/pipelines/{run['id']}/{action}/", data, content_type="application/json")

    def step(self, run):
        response = self.action(run, "advance", {"step": run["step"]})
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["run"]

    def run_batch(self, mode, fixture="november.csv", content=None):
        run = self.upload(mode, fixture, content=content)["run"]
        while run["status"] == "in_progress":
            run = self.step(run)
        return run

    def table(self, name):
        return self.client.get("/api/warehouse/", {"table": name}).json()

    def comparison(self):
        return self.client.get("/api/pipelines/compare/", {"month": "2026-11"}).json()

    def test_etl_transforms_outside_the_warehouse_and_elt_loads_raw_first(self):
        etl = self.upload("etl")["run"]
        self.assertEqual(self.action(etl, "advance", {"step": 2}).status_code, 409)
        etl = self.step(self.step(etl))
        self.assertEqual(etl["clean_preview"][0][3], "1250.00")
        self.assertEqual(self.table("staging.orders")["total"], 0)
        self.assertEqual(self.table("raw.orders")["total"], 0)
        etl = self.step(etl)
        elt = self.step(self.step(self.upload("elt")["run"]))
        self.assertEqual(self.table("raw.orders")["rows"][0][-1], "₱1,250.00")
        elt = self.step(elt)
        self.assertEqual([etl["revenue"], elt["revenue"]], ["2000.00", "2000.00"])
        self.assertEqual(etl["clean_preview"], elt["clean_preview"])
        self.assertEqual(self.comparison()["different_orders"], 0)
        self.assertTrue(self.comparison()["matches"])
        repeated = self.upload("elt")
        self.assertTrue(repeated["reused"])
        self.assertEqual(repeated["run"]["id"], elt["id"])
        self.assertEqual(self.table("raw.orders")["total"], 2)
        self.assertEqual(len(self.client.get("/api/pipelines/").json()["runs"]), 2)

    def test_review_and_invalid_replacement_preserve_published_batch(self):
        initial = self.run_batch("elt")
        correction = self.run_batch("elt", "november-corrected.csv")
        self.assertEqual(correction["status"], "review")
        self.assertEqual(correction["replacement"]["id"], initial["id"])
        self.assertEqual(self.comparison()["elt"]["revenue"], "2000.00")
        response = self.action(correction, "publish", {"baseline": initial["id"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["run"]["status"], "published")
        self.assertEqual(self.comparison()["elt"]["revenue"], "1300.00")
        self.assertEqual(self.table("mart.daily_sales")["total"], 1)
        bad = self.run_batch("elt", "november-invalid.csv")
        self.assertEqual(bad["status"], "failed")
        self.assertEqual(bad["error_count"], 2)
        self.assertEqual(bad["errors"][0], {"row": 2, "message": "Duplicate order ID."})
        self.assertEqual(len(bad["source_preview"]), 2)
        self.assertEqual(self.comparison()["elt"]["revenue"], "1300.00")

    def test_stale_replacement_needs_a_fresh_review(self):
        initial = self.run_batch("etl")
        correction = self.run_batch("etl", "november-corrected.csv")
        other = self.run_batch("etl", content=b"order_id,order_date,amount\nORD-001,2026-11-05,1400\n")
        self.assertEqual(self.action(other, "publish", {"baseline": initial["id"]}).status_code, 200)
        self.assertEqual(self.action(correction, "publish", {"baseline": initial["id"]}).status_code, 409)
        self.assertEqual(self.comparison()["etl"]["revenue"], "1400.00")
        refreshed = self.client.get(f"/api/pipelines/{correction['id']}/").json()["run"]
        self.assertEqual(refreshed["replacement"]["id"], other["id"])
        self.assertEqual(self.action(refreshed, "publish", {"baseline": other["id"]}).status_code, 200)
        self.assertEqual(self.comparison()["etl"]["revenue"], "1300.00")

    def test_workspaces_and_mutating_requests_are_isolated(self):
        run = self.run_batch("elt")
        member = self.session("member")
        self.assertEqual(member.get("/api/pipelines/").json()["runs"], [])
        self.assertEqual(member.get(f"/api/pipelines/{run['id']}/").status_code, 404)
        self.assertEqual(
            self.send(member, f"/api/pipelines/{run['id']}/advance/", {"step": 0}, content_type="application/json").status_code,
            404,
        )
        self.assertEqual(member.get("/api/warehouse/", {"table": "raw.orders"}).json()["total"], 0)
        self.assertEqual(self.client.post("/api/pipelines/").status_code, 403)
        self.assertEqual(Client().get("/api/warehouse/").status_code, 401)

    def test_date_and_amount_validation_match_in_both_modes(self):
        source = (
            'order_id,order_date,amount\n'
            'valid,2026-11-10," ₱ 1,050.1 "\n'
            'other-month,2026-10-20,2\n'
            'bad-date,2026-11-31,3\n'
            'too-precise,2026-11-11,12.345\n'
            'too-high,2026-11-11,10000000000\n'
            'bad-separators,2026-11-11,"12,50"\n'
            ',2026-11-11,10\n'
        ).encode()
        etl = self.run_batch("etl", content=source)
        elt = self.run_batch("elt", content=source)
        self.assertEqual((etl["status"], elt["status"]), ("failed", "failed"))
        self.assertEqual((etl["row_count"], elt["row_count"]), (1, 1))
        self.assertEqual(len(elt["errors"]), 6)
        self.assertEqual(etl["errors"], elt["errors"])

    def test_invalid_header_fails_extract_without_creating_rows(self):
        run = self.run_batch("elt", content=b"id,date,amount\n1,2026-11-12,20\n")
        self.assertEqual(run["status"], "failed")
        self.assertIn("CSV columns", run["error"])
        self.assertEqual(self.table("raw.orders")["total"], 0)

    def test_samples_and_table_names_are_bounded(self):
        path = "/api/pipelines/samples/november.csv/"
        sample = self.client.get(path)
        self.assertEqual(sample.status_code, 200)
        self.assertEqual(b"".join(sample.streaming_content), (FIXTURES / "november.csv").read_bytes())
        self.assertEqual(Client().get(path).status_code, 401)
        self.assertEqual(self.client.get("/api/pipelines/samples/other.csv/").status_code, 404)
        self.assertEqual(self.client.get("/api/warehouse/", {"table": "runs"}).status_code, 400)
