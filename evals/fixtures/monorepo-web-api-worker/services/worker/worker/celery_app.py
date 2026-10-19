import os

import sentry_sdk
from celery import Celery

sentry_sdk.init(dsn=os.environ.get("SENTRY_DSN"))

app = Celery("worker", broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"))


@app.task
def ping():
    return "pong"
