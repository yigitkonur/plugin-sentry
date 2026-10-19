import os

import sentry_sdk
from fastapi import FastAPI

sentry_sdk.init(dsn=os.environ.get("SENTRY_DSN"), traces_sample_rate=0.2)

app = FastAPI()


@app.get("/health")
def health():
    return {"ok": True}
