from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    app_name: str = "AgentSaaS"
    debug: bool = False
    
    # Supabase
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_anon_key: str = ""
    
    # OpenAI
    openai_api_key: str = ""
    
    # Auth
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    
    # OpenAI
    default_model: str = "gpt-4o-mini"
    default_temperature: float = 0.7
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
