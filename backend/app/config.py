from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./aioac.db"
    storage_dir: str = "./storage"
    payment_provider: str = "mock"  # mock | paypal
    training_backend: str = "local"  # local | sagemaker
    llm_provider: str = "openrouter"
    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-sonnet-4.5"  # set in .env; check current OpenRouter model ids
    hf_token: str = ""  # optional; public datasets work without it
    max_fetch_rows: int = 50_000
    max_fetch_bytes: int = 50_000_000
    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_webhook_id: str = ""

    # Budget policy (specs/cost.md). All money in cents.
    aws_budget_cents: int = 16000
    reserve_cents: int = 4000            # kept untouched for demo and recording
    max_job_cap_cents: int = 700         # hard per-job maximum
    quote_ttl_minutes: int = 60
    candidate_ttl_hours: int = 24
    agent_max_steps: int = 12


settings = Settings()
