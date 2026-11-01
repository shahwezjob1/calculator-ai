from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://calculator:calculator@localhost:5432/calculator"
    server_port: int = 8001
    reviewer_service_url: str = "http://localhost:8002"
    exec_timeout_seconds: float = 2.0
    exec_memory_limit_mb: int = 128
    db_pool_min_size: int = 1
    db_pool_max_size: int = 10
    log_level: str = "INFO"


settings = Settings()
