from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://medichain:medichain@localhost:5432/medichain"
    REDIS_URL: str = "redis://localhost:6379"
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    KIMI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    MEDICHAIN_LLM_MODEL: str = "kimi"
    APP_ENV: str = "development"
    DEBUG: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
