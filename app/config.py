from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'ClearView Moderator Service'
    nsfw_threshold: float = 0.8
    image_max_side: int = 1024
    openai_model: str = 'omni-moderation-latest'
    openai_timeout_seconds: float = 10.0
    easyocr_languages: list[str] = ['en']
    use_gpu: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
