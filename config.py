from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    LLM_API_KEY: str = ""
    LLM_PROVIDER: str = "proxyapi_gemini"
    LLM_MODEL: str = "gemini-2.0-flash"
    LLM_BASE_URL: str = "https://api.proxyapi.ru/google/v1beta"
    LLM_TIMEOUT_SEC: int = 60
    LLM_MAX_INPUT_CHARS: int = 12000
    LLM_MAX_OUTPUT_CHARS: int = 5000

    HOTKEY: str = "Ctrl+Shift+Space"
    LOG_FILE: str = "error_log.txt"
    LOG_CLEAR_INTERVAL_SECONDS: int = 3600


settings = Settings()
