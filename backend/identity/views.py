import hashlib
import json
import re
import secrets
from datetime import timedelta
from functools import wraps

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .models import Account, AccountEvent, SetupLink

User = get_user_model()
USERNAME = re.compile(r"[a-z0-9][a-z0-9._-]{2,31}")
TOKEN = re.compile(r"[\w-]{43}", re.ASCII)
REVISION = "autumnleaf_session_revision"


def error(message, status=400):
    return JsonResponse({"error": message}, status=status)


def body(request):
    try:
        value = json.loads(request.body)
    except (ValueError, UnicodeError):
        return {}
    return value if isinstance(value, dict) else {}


def account_json(account):
    return {
        "id": str(account.pk),
        "username": account.user.username,
        "role": account.role,
        "status": account.status,
    }


def current_account(request):
    if not request.user.is_authenticated:
        return None
    account = Account.objects.select_related("user").filter(user=request.user).first()
    if account and request.session.get(REVISION) == account.session_revision:
        return account
    logout(request)
    return None


def signed_in(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        account = current_account(request)
        if not account:
            return error("Sign in to continue.", 401)
        return view(request, account, *args, **kwargs)

    return wrapped


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def issue_link(account):
    token = secrets.token_urlsafe(32)
    SetupLink.objects.update_or_create(
        account=account,
        defaults={"digest": digest(token), "expires_at": timezone.now() + timedelta(hours=24)},
    )
    return token


def can_manage(request, actor):
    return (
        actor.role == Account.Role.ADMIN
        and actor.user.is_active
        and request.session.get(REVISION) == actor.session_revision
    )


@never_cache
def csrf_failure(request, reason=""):
    return error("This request could not be verified. Reload and try again.", 403)


@never_cache
@require_GET
def csrf(request):
    return JsonResponse({"csrfToken": get_token(request)})


@never_cache
@require_GET
@signed_in
def session(request, account):
    return JsonResponse({"account": account_json(account)})


@never_cache
@require_POST
def sign_in(request):
    data = body(request)
    username, password = data.get("username"), data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return error("Enter a username and password.")
    username = username.strip().lower()
    if not USERNAME.fullmatch(username) or not 0 < len(password) <= 128:
        return error("Incorrect username or password.", 401)
    user = authenticate(request, username=username, password=password)
    account = Account.objects.select_related("user").filter(user=user).first() if user else None
    if not account or not account.user.is_active:
        return error("Incorrect username or password.", 401)
    login(request, user)
    request.session[REVISION] = account.session_revision
    return JsonResponse({"account": account_json(account)})


@never_cache
@require_POST
def sign_out(request):
    logout(request)
    return JsonResponse({"signedOut": True})


@never_cache
@require_POST
@transaction.atomic
def set_password(request):
    data = body(request)
    token, password = data.get("token"), data.get("password")
    if not isinstance(token, str) or not TOKEN.fullmatch(token):
        return error("This link is invalid or has expired.")
    if not isinstance(password, str) or not 0 < len(password) <= 128:
        return error("Enter a password of up to 128 characters.")

    checksum = digest(token)
    account_id = SetupLink.objects.filter(digest=checksum).values_list("account_id", flat=True).first()
    if not account_id:
        return error("This link is invalid or has expired.")
    account = Account.objects.select_for_update().select_related("user").get(pk=account_id)
    link = SetupLink.objects.filter(account=account, digest=checksum, expires_at__gt=timezone.now()).first()
    if not link or not account.user.is_active:
        return error("This link is invalid or has expired.")
    try:
        validate_password(password, account.user)
    except ValidationError as exc:
        return error(" ".join(exc.messages))

    account.user.set_password(password)
    account.user.save(update_fields=["password"])
    account.session_revision += 1
    account.save(update_fields=["session_revision"])
    link.delete()
    if request.user.is_authenticated and request.user.pk == account.user_id:
        logout(request)
    return JsonResponse({"passwordSet": True})


@never_cache
@require_GET
@signed_in
def workspace(request, account, account_id):
    if account.pk != account_id:
        return error("Workspace not found.", 404)
    return JsonResponse({"workspace": {"id": str(account.pk), "name": "Personal workspace"}})


@never_cache
@require_http_methods(["GET", "POST"])
@signed_in
def accounts(request, actor):
    if not can_manage(request, actor):
        return error("Only Admins can manage accounts.", 403)
    if request.method == "GET":
        rows = Account.objects.select_related("user").order_by("user__username")
        return JsonResponse({"accounts": [account_json(row) for row in rows]})

    data = body(request)
    username = data.get("username")
    role = data.get("role", Account.Role.MEMBER)
    if not isinstance(username, str) or not USERNAME.fullmatch(username.strip().lower()):
        return error("Use 3–32 letters, numbers, dots, hyphens, or underscores for the username.")
    if role not in Account.Role.values:
        return error("Select Member or Admin.")
    try:
        with transaction.atomic():
            actor = Account.objects.select_for_update().select_related("user").get(pk=actor.pk)
            if not can_manage(request, actor):
                return error("Only Admins can manage accounts.", 403)
            user = User.objects.create_user(username=username.strip().lower())
            account = Account.objects.create(user=user, role=role)
            token = issue_link(account)
            AccountEvent.objects.create(actor=actor, target=account, action="created")
    except IntegrityError:
        return error("That username is already in use.", 409)
    return JsonResponse({"account": account_json(account), "token": token}, status=201)


@never_cache
@require_http_methods(["PATCH"])
@signed_in
@transaction.atomic
def manage_account(request, actor, account_id):
    if not can_manage(request, actor):
        return error("Only Admins can manage accounts.", 403)

    locked = {
        row.pk: row
        for row in Account.objects.select_for_update().select_related("user")
        .filter(pk__in={actor.pk, account_id}).order_by("pk")
    }
    actor = locked[actor.pk]
    if not can_manage(request, actor):
        return error("Only Admins can manage accounts.", 403)
    account = locked.get(account_id)
    if not account:
        return error("Account not found.", 404)
    if account.pk == actor.pk:
        return error("You cannot manage your own account here.", 403)

    data = body(request)
    action = data.get("action")
    response = {}
    if action == "disable":
        account.user.is_active = False
        account.user.save(update_fields=["is_active"])
        account.session_revision += 1
        account.save(update_fields=["session_revision"])
        SetupLink.objects.filter(account=account).delete()
    elif action == "reactivate":
        account.user.is_active = True
        account.user.save(update_fields=["is_active"])
    elif action == "set_role":
        role = data.get("role")
        if role not in Account.Role.values:
            return error("Select Member or Admin.")
        account.role = role
        account.save(update_fields=["role"])
    elif action == "issue_link":
        if not account.user.is_active:
            return error("Reactivate this account before issuing a link.")
        response["token"] = issue_link(account)
    else:
        return error("Unknown account action.")

    AccountEvent.objects.create(actor=actor, target=account, action=action)
    return JsonResponse({"account": account_json(account), **response})
