from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    UPLOAD_DIR: Path = Path("uploads")


settings = Settings()
