import logging
import os

import sentry_sdk
from fastapi import FastAPI
from sentry_sdk.integrations.logging import LoggingIntegration

from app import jobs
from app.llm import answer

app = FastAPI(title="acme-api")

sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN"),
    send_default_pii=True,
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
    include_local_variables=True,
    _experiments={"enable_logs": True},
    integrations=[LoggingIntegration(level=logging.INFO, event_level=logging.INFO)],
)


@app.on_event("startup")
def start_scheduler() -> None:
    jobs.scheduler.start()


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/ask")
def ask(q: str, user_email: str) -> dict:
    return {"answer": answer(q, user_email)}
