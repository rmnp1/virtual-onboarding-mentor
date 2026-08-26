from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/db.sqlite"
    secret_key: str = "change-me-in-production"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    jwt_expire_minutes: int = 1440

    model_config = {"env_file": ".env"}


settings = Settings()
