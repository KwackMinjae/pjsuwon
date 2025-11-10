import base64
import os
import uuid
from typing import Optional

import httpx

from app.settings import settings


class AILabError(Exception):
    pass


class MeshyError(Exception):
    pass


# ---------- 공통: 로컬 파일 저장 유틸 ----------

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def save_bytes_to_file(root: str, prefix: str, data: bytes, ext: str) -> str:
    ensure_dir(root)
    name = f"{prefix}_{uuid.uuid4().hex}{ext}"
    path = os.path.join(root, name)
    with open(path, "wb") as f:
        f.write(data)
    return path  # 상대 경로 그대로 반환


# ---------- AILab: 헤어스타일 합성 (옵션) ----------

async def try_ailab_hairstyle(image_bytes: bytes, hair_type: Optional[int] = None) -> Optional[str]:
    """
    AILab 헤어스타일 변경 시도.
    - 성공: 결과 이미지를 outputs 폴더에 저장하고 그 경로를 문자열로 리턴.
    - 실패/키없음: None 리턴.
    """
    if not settings.ailab_api_key:
        return None

    url = f"{settings.ailab_base_url}/api/portrait/effects/hairstyle-editor"
    headers = {
        "ailabapi-api-key": settings.ailab_api_key,
    }

    data = {}
    if hair_type is not None:
        data["hair_type"] = str(hair_type)

    files = {
        "image_target": ("input.jpg", image_bytes, "image/jpeg"),
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, data=data, files=files)
        resp.raise_for_status()
        body = resp.json()

        if body.get("error_code") != 0:
            return None

        data_field = body.get("data") or {}

        # base64 이미지 케이스
        b64_img = data_field.get("image")
        if isinstance(b64_img, str) and b64_img:
            try:
                img_bytes = base64.b64decode(b64_img)
                return save_bytes_to_file(settings.outputs_root, "ailab_hair", img_bytes, ".png")
            except Exception:
                return None

        # URL 케이스
        url_img = data_field.get("url")
        if isinstance(url_img, str) and url_img:
            return url_img

        return None
    except Exception:
        return None


# ---------- Meshy: Image → 3D ----------

async def create_meshy_image_to_3d(image_url: str) -> str:
    """
    Meshy Image-to-3D Task 생성.
    성공 시 task_id 반환.
    """
    if not settings.meshy_api_key:
        raise MeshyError("MESHY_API_KEY 가 설정되어 있지 않습니다 (.env 확인).")

    endpoint = f"{settings.meshy_base_url}/openapi/v1/image-to-3d"
    headers = {
        "Authorization": f"Bearer {settings.meshy_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "image_url": image_url,
        "should_remesh": True,
        "should_texture": True,
        "enable_pbr": True,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(endpoint, headers=headers, json=payload)
    if resp.status_code >= 400:
        raise MeshyError(f"Meshy 요청 실패: {resp.status_code} {resp.text}")

    data = resp.json()
    task_id = data.get("result")
    if not task_id:
        raise MeshyError(f"Meshy 응답에 task_id(result)가 없습니다: {data}")
    return task_id


async def get_meshy_task(task_id: str) -> dict:
    """
    Meshy Task 상태를 '한 번만' 조회.
    - 성공: task 객체(dict) 반환
    - 실패: MeshyError 발생
    """
    if not settings.meshy_api_key:
        raise MeshyError("MESHY_API_KEY 가 설정되어 있지 않습니다.")

    endpoint = f"{settings.meshy_base_url}/openapi/v1/image-to-3d/{task_id}"
    headers = {
        "Authorization": f"Bearer {settings.meshy_api_key}",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(endpoint, headers=headers)
    if resp.status_code >= 400:
        raise MeshyError(f"Meshy 조회 실패: {resp.status_code} {resp.text}")

    return resp.json()


def extract_glb_url(task_data: dict) -> Optional[str]:
    """
    Meshy Task 응답에서 GLB URL만 추출.
    """
    model_urls = task_data.get("model_urls") or {}
    glb = model_urls.get("glb")
    return glb

async def require_ailab_hairstyle(image_bytes: bytes, hair_type: Optional[int] = None) -> str:
    """
    AILab 헤어 합성을 '필수'로 사용할 때 쓰는 헬퍼.
    - 성공: fused_image_path 또는 URL 반환
    - 실패: AILabError 예외 발생
    """
    result = await try_ailab_hairstyle(image_bytes, hair_type=hair_type)
    if not result:
        raise AILabError("AILab 헤어 합성에 실패했습니다. API 키, 플랜, 엔드포인트를 확인하세요.")
    return result

async def debug_ailab_hairstyle(image_bytes: bytes, hair_type: Optional[int] = None) -> dict:
    """
    AILab 요청/응답을 그대로 확인하기 위한 디버그용 함수.
    - 실제로 어떤 URL에 어떤 헤더/응답 코드가 오고 있는지 확인용.
    """
    if not settings.ailab_api_key:
        raise AILabError("AILAB_API_KEY 가 설정되어 있지 않습니다.")

    url = f"{settings.ailab_base_url}/api/portrait/effects/hairstyle-editor"
    headers = {
        "ailabapi-api-key": settings.ailab_api_key,
    }

    data = {}
    if hair_type is not None:
        data["hair_type"] = str(hair_type)

    files = {
        "image_target": ("input.jpg", image_bytes, "image/jpeg"),
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=headers, data=data, files=files)

    # 응답 바디를 JSON 시도 후, 아니면 text로 반환
    try:
        body = resp.json()
    except Exception:
        body = resp.text

    return {
        "request_url": url,
        "status_code": resp.status_code,
        "response": body,
    }
