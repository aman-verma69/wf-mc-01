"""
Central configuration. Every secret/API key in the whole app is read
ONLY from here (never os.getenv() scattered around the codebase).

Fill in the real values in a .env file at the repo root (copy .env.example).
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    APP_ENV: str = "development"
    APP_SECRET_KEY: str = "change-me"

    # --- Authentication ---
    JWT_SECRET_KEY: str = "change-me-jwt-secret-at-least-32-bytes"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    IDEMPOTENCY_PROCESSING_TIMEOUT_SECONDS: int = 300

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/commerce"

    # --- Razorpay (payments — required) ---
    # https://dashboard.razorpay.com/app/keys
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    # Dashboard > Webhooks > set a secret when you register the webhook URL
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # --- LLM backends for agents ---
    # Grok (x.ai) — https://console.x.ai
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_MODEL: str = "openai/gpt-oss-20b"

    # gpt-oss-20B — self-hosted (vLLM / Ollama / etc). Point this at your
    # own inference server; there is no Anthropic/OpenAI-hosted endpoint for it.
    GPT_OSS_BASE_URL: str = "http://localhost:11434/v1"
    GPT_OSS_API_KEY: str = ""  # only needed if your server gates on a key
    GPT_OSS_MODEL: str = "gpt-oss:20b"

    # --- Tavily (web search for Catalog / Growth agents) ---
    # https://app.tavily.com
    TAVILY_API_KEY: str = ""

    # --- Notifications (optional, used by services/notification_service.py) ---
    SMTP_HOST: str = ""
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    WHATSAPP_API_KEY: str = ""  # if using a WhatsApp Business provider

    # --- Guardrail defaults (policy/guardrail.py) ---
    MAX_AUTONOMOUS_SPEND_PAISE: int = 500000  # ₹5,000 — above this, require human confirmation
    REQUIRE_HUMAN_CONFIRMATION_ABOVE_LIMIT: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
