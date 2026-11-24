import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.core.management.utils import get_random_secret_key

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get("AUTUMNLEAF_DEBUG") == "1"
SECRET_KEY = os.environ.get("AUTUMNLEAF_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Set AUTUMNLEAF_SECRET_KEY outside local development.")
    SECRET_KEY = get_random_secret_key()

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("AUTUMNLEAF_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")
    if host.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "AUTUMNLEAF_CSRF_TRUSTED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173" if DEBUG else "",
    ).split(",")
    if origin.strip()
]
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "identity",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
CSRF_FAILURE_VIEW = "identity.views.csrf_failure"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("AUTUMNLEAF_SQLITE_PATH", BASE_DIR / "db.sqlite3"),
        "OPTIONS": {"transaction_mode": "IMMEDIATE"},
    }
}
WAREHOUSE_ROOT = Path(
    os.environ.get("AUTUMNLEAF_WAREHOUSE_DIR")
    or Path(DATABASES["default"]["NAME"]).parent / "warehouses"
)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
TIME_ZONE = "UTC"
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = not DEBUG
