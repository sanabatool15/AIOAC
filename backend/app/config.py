from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./aioac.db"
    payment_provider: str = "mock"  # mock | paypal
    training_backend: str = "local"  # local | sagemaker
    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_webhook_id: str = ""
    openrouter_api_key: str = ""
    max_spend_cap_cents: int = 2000  # hard ceiling for any single job


settings = Settings()
