import os
from pathlib import Path

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only")
DEBUG = os.environ.get("DEBUG", "0") == "1"
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "app",
]
MIDDLEWARE = ["django.middleware.common.CommonMiddleware"]
ROOT_URLCONF = "config.urls"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "app"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
    }
}
CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

sentry_sdk.init(dsn=os.environ.get("SENTRY_DSN"), traces_sample_rate=1.0, send_default_pii=True, integrations=[DjangoIntegration()])
