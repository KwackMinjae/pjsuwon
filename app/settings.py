from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    aws_region: str = Field(..., alias="AWS_REGION")
    aws_s3_bucket: str = Field(..., alias="AWS_S3_BUCKET")
    aws_access_key_id: str | None = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
    allowed_origins: str | None = Field(default=None, alias="ALLOWED_ORIGINS")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
