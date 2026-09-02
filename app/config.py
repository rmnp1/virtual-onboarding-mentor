from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/db.sqlite"
    secret_key: str = "unset"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    ollama_embedding_model: str = "nomic-embed-text"
    jwt_expire_minutes: int = 1440
    chroma_persist_dir: str = "./data/chroma"
    cors_origins: str = ""
    expose_docs: bool = True
    invite_required: bool = False
    invite_codes: str = ""

    model_config = {"env_file": ".env"}

    @model_validator(mode="after")
    def _validate_secret_key(self) -> Self:
        if len(self.secret_key) < 32:
            raise ValueError("SECRET_KEY must be set and at least 32 characters long")
        return self


settings = Settings()
