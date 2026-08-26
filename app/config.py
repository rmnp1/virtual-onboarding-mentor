from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/db.sqlite"
    secret_key: str = "change-me-in-production"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    ollama_embedding_model: str = "nomic-embed-text"
    jwt_expire_minutes: int = 1440
    chroma_persist_dir: str = "./data/chroma"

    model_config = {"env_file": ".env"}


settings = Settings()
