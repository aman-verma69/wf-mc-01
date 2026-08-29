from fastapi import FastAPI

from backend.api.v1 import agents, checkout, payments, webhooks
from backend.observability.logging_config import configure_logging

configure_logging()

app = FastAPI(title="AI Commerce Platform", version="0.1.0")

app.include_router(agents.router, prefix="/api/v1")
app.include_router(checkout.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
