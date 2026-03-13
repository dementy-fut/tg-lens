from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_api_id: int
    telegram_api_hash: str
    telegram_phone: str
    supabase_url: str
    supabase_service_key: str
    anthropic_api_key: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
