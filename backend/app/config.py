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
    # Agent limits (specs/agent.md section 2). Not money the user pays: this is our own model bill.
    agent_max_tokens_per_turn: int = 80_000
    agent_max_tokens_per_project: int = 600_000
    agent_llm_cost_ceiling_usd: float = 1.00   # per project, only enforced when the model service reports cost
    agent_tool_timeout_s: float = 60.0         # free tools only; paid tools are never cut off by this


settings = Settings()
