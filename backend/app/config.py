from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Engineering Workflow Manager"
    database_url: str = "postgresql+psycopg://workflow:workflow@localhost:5432/workflow"
    frontend_origin: str = "http://localhost:5173"
    default_user_id: str = "user-001"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
