import os
from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from app.settings import settings

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.get("/{filename}")
async def get_file(filename: str):
    """
    로컬 uploads/ 폴더에 저장된 파일 서빙용.
    실제 서비스에서는 nginx나 S3로 대체 가능.
    """
    path = os.path.join(settings.media_root, filename)
    if not os.path.exists(path):
        return JSONResponse(status_code=404, content={"detail": "File not found"})
    return FileResponse(path)
