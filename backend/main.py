from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.v1 import agents, checkout, customers, orders, payments, webhooks
from backend.observability.logging_config import configure_logging

configure_logging()

app = FastAPI(title="AI Commerce Platform", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router, prefix="/api/v1")
app.include_router(customers.router, prefix="/api/v1")
app.include_router(orders.router, prefix="/api/v1")
app.include_router(checkout.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}