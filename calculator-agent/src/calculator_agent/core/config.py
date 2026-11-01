from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Make .env visible to libraries that read os.environ directly (e.g. the Gemini client).
load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "google_genai"
    llm_model: str = "gemini-2.5-flash"
    title_llm_provider: str = "google_genai"
    title_llm_model: str = "gemini-2.5-flash-lite"
    google_api_key: str = ""
    database_url: str = "postgresql://calculator:calculator@localhost:5432/calculator"
    calculator_service_url: str = "http://localhost:8001"
    reviewer_service_url: str = "http://localhost:8002"
    server_port: int = 8000
    db_pool_min_size: int = 1
    db_pool_max_size: int = 10
    log_level: str = "INFO"


settings = Settings()
