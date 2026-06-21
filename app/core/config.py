from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    app_name: str = "FQ-SaaS"
    debug: bool = False
    environment: str = "development"
    version: str = "0.1.0"
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Auth / JWT
    secret_key: str = "change-me-in-production"
    fernet_key: str = "change-me-in-production-generate-with-fernet"

    def model_post_init(self, __context) -> None:
        is_production = self.environment.lower() == "production"
        if not is_production:
            return
        if self.secret_key == "change-me-in-production" or len(self.secret_key) < 32:
            raise RuntimeError("SECURITY ERROR: SECRET_KEY is still the default value. Set a strong secret key in .env (at least 32 characters).")
        if self.fernet_key in {
            "change-me-in-production",
            "change-me-in-production-generate-with-fernet",
            "replace-with-a-fernet-key",
        }:
            raise RuntimeError("SECURITY ERROR: FERNET_KEY is still the default value. Generate one: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'")
        try:
            Fernet(self.fernet_key.encode())
        except Exception as exc:
            raise RuntimeError("SECURITY ERROR: FERNET_KEY must be a valid Fernet key.") from exc
        if self.postgres_password in {"postgres", "password", "change-me", "replace-with-strong-postgres-password"}:
            raise RuntimeError("SECURITY ERROR: POSTGRES_PASSWORD is still the default value. Set a strong password in .env.")
        if self.hermes_orchestrator_url and len(self.hermes_orchestrator_secret) < 32:
            raise RuntimeError("SECURITY ERROR: HERMES_ORCHESTRATOR_SECRET must be at least 32 characters in production.")
        if self.llm_provider not in {"minimax", "openai", "ollama"}:
            raise RuntimeError("SECURITY ERROR: LLM_PROVIDER must be minimax, openai, or ollama in production.")
        if self.is_minimax and not self.minimax_api_key:
            raise RuntimeError("SECURITY ERROR: MINIMAX_API_KEY is required when LLM_PROVIDER=minimax.")
        if self.is_openai and not self.openai_api_key:
            raise RuntimeError("SECURITY ERROR: OPENAI_API_KEY is required when LLM_PROVIDER=openai.")
        if "*" in self.allowed_origins:
            raise RuntimeError("SECURITY ERROR: ALLOWED_ORIGINS cannot contain '*' in production.")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    invite_token_ttl_hours: int = 72
    telegram_bind_code_ttl_minutes: int = 30

    # Database
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "fqsaas"
    postgres_host: str = "localhost"
    postgres_port: int = 5433
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/fqsaas"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    rate_limit_backend: str = "redis"
    rate_limit_per_minute: int = 100
    auth_rate_limit_per_minute: int = 10
    websocket_max_message_bytes: int = 32768
    kpi_token_alert_threshold: int = 40000
    kpi_cost_alert_threshold: float = 25.0

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"

    # LLM Provider
    llm_provider: str = "mock"
    default_model: str = "qwen3-14b"
    minimax_api_key: str = ""
    minimax_base_url: str = "https://api.minimax.chat/v1/text/chatcompletion-v2"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1/chat/completions"
    ollama_base_url: str = "http://localhost:11434"

    # Hermes runtime / orchestrator
    hermes_orchestrator_url: str = ""
    hermes_orchestrator_secret: str = ""
    hermes_request_timeout_seconds: float = 120.0

    # Telegram
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    telegram_webhook_url: str = ""

    # Observability
    sentry_dsn: str = ""
    sentry_environment: str = ""
    sentry_traces_sample_rate: float = 0.0
    alert_notification_emails: str = ""
    alert_notification_cooldown_minutes: int = 60

    # SMTP / Email
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@fqsaas.local"

    @property
    def is_minimax(self) -> bool:
        return self.llm_provider == "minimax"

    @property
    def is_openai(self) -> bool:
        return self.llm_provider == "openai"

    @property
    def is_ollama(self) -> bool:
        return self.llm_provider == "ollama"

    @property
    def is_mock(self) -> bool:
        return self.llm_provider == "mock"

    @property
    def alert_notification_recipients(self) -> list[str]:
        return [item.strip() for item in self.alert_notification_emails.split(",") if item.strip()]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
