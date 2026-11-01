from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Make .env visible to libraries that read os.environ directly (e.g. the Gemini client).
load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    review_llm_provider: str = "google_genai"
    review_llm_model: str = "gemini-2.5-flash"
    google_api_key: str = ""
    server_port: int = 8002
    log_level: str = "INFO"


settings = Settings()
