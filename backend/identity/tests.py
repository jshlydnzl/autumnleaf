import json
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .models import Account, AccountEvent, SetupLink
from .views import digest

User = get_user_model()
PASSWORD = "Workshop-click-84-Observer"
NEW_PASSWORD = "Fern-Cloud-Receipt-581"


def submit(client, path, data, method="post", **headers):
    return getattr(client, method)(path, json.dumps(data), content_type="application/json", **headers)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class IdentityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = Account.objects.create(
            user=User.objects.create_user(username="owner", password=PASSWORD), role=Account.Role.ADMIN
        )
        cls.member = Account.objects.create(user=User.objects.create_user(username="member", password=PASSWORD))

    def sign_in(self, name, password=PASSWORD, client=None):
        client = client or Client()
        response = submit(client, "/api/auth/login/", {"username": name, "password": password})
        self.assertEqual(response.status_code, 200, response.content)
        return client

    def issue(self, client, account):
        return submit(client, f"/api/accounts/{account.pk}/", {"action": "issue_link"}, "patch")

    def test_csrf_sign_in_sign_out(self):
        client = Client(enforce_csrf_checks=True)
        path = "/api/auth/login/"
        data = {"username": "owner", "password": PASSWORD}
        self.assertEqual(submit(client, path, data).status_code, 403)
        token = client.get("/api/auth/csrf/").json()["csrfToken"]
        self.assertEqual(submit(client, path, data, HTTP_X_CSRFTOKEN=token).status_code, 200)
        self.assertEqual(client.get("/api/auth/session/").status_code, 200)
        token = client.get("/api/auth/csrf/").json()["csrfToken"]
        self.assertEqual(submit(client, "/api/auth/logout/", {}, HTTP_X_CSRFTOKEN=token).status_code, 200)
        self.assertEqual(client.get("/api/auth/session/").status_code, 401)

    def test_member_cannot_manage_accounts_or_read_other_workspace(self):
        signed_out = Client()
        member = self.sign_in("member")
        admin = self.sign_in("owner")
        self.assertEqual(signed_out.get("/api/accounts/").status_code, 401)
        self.assertEqual(member.get("/api/accounts/").status_code, 403)
        self.assertEqual(submit(member, "/api/accounts/", {"username": "new"}).status_code, 403)
        self.assertEqual(self.issue(member, self.owner).status_code, 403)
        self.assertEqual(member.get(f"/api/workspaces/{self.member.pk}/").status_code, 200)
        self.assertEqual(member.get(f"/api/workspaces/{self.owner.pk}/").status_code, 404)
        self.assertEqual(admin.get(f"/api/workspaces/{self.member.pk}/").status_code, 404)

    def test_create_pending_member_and_redeem_once(self):
        owner = self.sign_in("owner")
        response = submit(owner, "/api/accounts/", {"username": " Invitee "})
        self.assertEqual(response.status_code, 201)
        account = response.json()["account"]
        token = response.json()["token"]
        self.assertEqual((account["role"], account["status"], account["username"]), ("member", "pending", "invitee"))
        self.assertEqual(SetupLink.objects.get(account_id=account["id"]).digest, digest(token))
        self.assertEqual(AccountEvent.objects.get().action, "created")
        visitor = Client()
        self.assertEqual(submit(visitor, "/api/auth/login/", {"username": "invitee", "password": NEW_PASSWORD}).status_code, 401)
        self.assertEqual(submit(visitor, "/api/auth/setup/", {"token": token, "password": "short"}).status_code, 400)
        invite = {"token": token, "password": NEW_PASSWORD}
        self.assertEqual(submit(visitor, "/api/auth/setup/", invite).status_code, 200)
        self.assertEqual(submit(visitor, "/api/auth/setup/", invite).status_code, 400)
        self.sign_in("invitee", NEW_PASSWORD)

    def test_reissued_and_expired_links_fail(self):
        owner = self.sign_in("owner")
        first = self.issue(owner, self.member).json()["token"]
        second = self.issue(owner, self.member).json()["token"]
        self.assertNotEqual(first, second)
        for token in (first, second):
            SetupLink.objects.filter(digest=digest(token)).update(expires_at=timezone.now() - timedelta(seconds=1))
            response = submit(Client(), "/api/auth/setup/", {"token": token, "password": NEW_PASSWORD})
            self.assertEqual(response.status_code, 400)

    def test_disable_revokes_old_sessions_even_after_reactivation(self):
        owner = self.sign_in("owner")
        old = self.sign_in("member")
        other = self.sign_in("member")
        path = f"/api/accounts/{self.member.pk}/"
        self.assertEqual(submit(owner, path, {"action": "disable"}, "patch").status_code, 200)
        self.assertEqual(old.get("/api/auth/session/").status_code, 401)
        self.assertEqual(submit(owner, path, {"action": "reactivate"}, "patch").status_code, 200)
        self.assertEqual(other.get("/api/auth/session/").status_code, 401)
        self.sign_in("member")

    def test_password_reset_revokes_old_session(self):
        owner = self.sign_in("owner")
        member = self.sign_in("member")
        token = self.issue(owner, self.member).json()["token"]
        self.assertEqual(submit(Client(), "/api/auth/setup/", {"token": token, "password": NEW_PASSWORD}).status_code, 200)
        self.assertEqual(member.get("/api/auth/session/").status_code, 401)
        self.sign_in("member", NEW_PASSWORD)

    def test_role_changes_apply_to_existing_session_and_self_management_is_blocked(self):
        owner = self.sign_in("owner")
        member = self.sign_in("member")
        self.assertEqual(submit(owner, f"/api/accounts/{self.owner.pk}/", {"action": "disable"}, "patch").status_code, 403)
        self.assertEqual(submit(owner, f"/api/accounts/{self.member.pk}/", {"action": "set_role", "role": "admin"}, "patch").status_code, 200)
        self.assertEqual(member.get("/api/accounts/").status_code, 200)
        self.assertEqual(submit(owner, f"/api/accounts/{self.member.pk}/", {"action": "set_role", "role": "member"}, "patch").status_code, 200)
        self.assertEqual(member.get("/api/accounts/").status_code, 403)

    def test_bootstrap_rejects_existing_admin_and_creates_first_without_default_password(self):
        with self.assertRaises(CommandError):
            call_command("bootstrap_admin", stdout=StringIO())
        self.owner.user.is_active = False
        self.owner.user.save(update_fields=["is_active"])
        with patch("builtins.input", return_value="new-admin"), patch(
            "identity.management.commands.bootstrap_admin.getpass", return_value=PASSWORD
        ):
            call_command("bootstrap_admin", stdout=StringIO())
        self.sign_in("new-admin")
