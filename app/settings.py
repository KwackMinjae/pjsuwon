from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # .env 읽기 + 이상한 환경변수 들어와도 무시
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Meshy
    meshy_api_key: Optional[str] = None
    meshy_base_url: str = "https://api.meshy.ai"

    # AILab (선택 사항, 없어도 서버 돌아가게)
    ailab_api_key: Optional[str] = None
    ailab_base_url: str = "https://www.ailabapi.com"

    # 파일 저장 경로 (로컬)
    media_root: str = "uploads"
    outputs_root: str = "outputs"


settings = Settings()
