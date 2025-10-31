from fastapi import APIRouter
from pydantic import BaseModel
from app.services.s3 import create_presigned_post

router = APIRouter(prefix="/uploads", tags=["uploads"])

class SignReq(BaseModel):
    key_prefix: str      # ¿¹: "faces" / "hairs"
    content_type: str    # ¿¹: "image/png"

@router.post("/sign")
def sign_upload(req: SignReq):
    return create_presigned_post(req.key_prefix, req.content_type)
