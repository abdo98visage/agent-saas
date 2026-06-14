from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    app_name: str = "FQ-SaaS"
    debug: bool = False
    version: str = "0.1.0"
    allowed_origins: list = ["http://localhost:3000", "http://localhost:8000"]

    # Auth / JWT
    secret_key: str = "change-me-in-production"
    fernet_key: str = "change-me-in-production-generate-with-fernet"

    def model_post_init(self, __context) -> None:
        if not self.debug and self.secret_key == "change-me-in-production":
            raise RuntimeError("SECURITY ERROR: SECRET_KEY is still the default value. Set a strong secret key in .env (at least 32 characters).")
        if not self.debug and self.fernet_key == "change-me-in-production-generate-with-fernet":
            raise RuntimeError("SECURITY ERROR: FERNET_KEY is still the default value. Generate one: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'")
        if not self.debug and self.postgres_password == "postgres":
            raise RuntimeError("SECURITY ERROR: POSTGRES_PASSWORD is still the default value. Set a strong password in .env.")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    # Database
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "fqsaas"
    postgres_host: str = "localhost"
    postgres_port: int = 5433
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/fqsaas"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"

    # LLM Provider
    llm_provider: str = "mock"
    minimax_api_key: str = ""
    minimax_base_url: str = "https://api.minimax.chat/v1/text/chatcompletion-v2"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1/chat/completions"
    ollama_base_url: str = "http://localhost:11434"

    # Hermes runtime / orchestrator
    hermes_orchestrator_url: str = ""
    hermes_orchestrator_secret: str = ""
    hermes_request_timeout_seconds: float = 30.0

    # Telegram
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    telegram_webhook_url: str = ""

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

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
