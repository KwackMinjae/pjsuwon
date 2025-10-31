import uuid
from datetime import datetime
import boto3
from app.settings import settings

# 지역/자격증명은 .env에서 로드
s3 = boto3.client(
    "s3",
    region_name=settings.aws_region,
    aws_access_key_id=settings.aws_access_key_id,
    aws_secret_access_key=settings.aws_secret_access_key,
)

def create_presigned_post(key_prefix: str, content_type: str, expires_in: int = 3600):
    # 파일 키 생성 (예: faces/20251028_153000_xxx.png)
    key = f"{key_prefix}/{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex}.png"

    fields = {"Content-Type": content_type}
    # Content-Type 계열만 starts-with 체크 (image/, video/ 등)
    conditions = [["starts-with", "$Content-Type", content_type.split("/")[0]]]

    post = s3.generate_presigned_post(
        Bucket=settings.aws_s3_bucket,
        Key=key,
        Fields=fields,
        Conditions=conditions,
        ExpiresIn=expires_in,
    )
    return {"url": post["url"], "fields": post["fields"], "key": key}
