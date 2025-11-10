from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Form,
    HTTPException,
    status,
    Query,
)
from fastapi.responses import StreamingResponse
from typing import Optional
import base64
import httpx
from urllib.parse import unquote

from app.settings import settings
from app.services.hairfusion_client import (
    save_bytes_to_file,
    try_ailab_hairstyle,
    require_ailab_hairstyle,
    create_meshy_image_to_3d,
    get_meshy_task,
    extract_glb_url,
    AILabError,
    debug_ailab_hairstyle,
)

router = APIRouter(prefix="/fusion", tags=["fusion"])


# ─────────────────────────────────────────────
# 1. AILab 합성 디버그용 (직접 응답 확인)
# ─────────────────────────────────────────────
@router.post("/ailab-test")
async def ailab_test(
    file: UploadFile = File(...),
    hair_type: Optional[int] = Form(None),
):
    """
    AILab API가 실제로 어떤 응답을 주는지 확인하기 위한 디버그 엔드포인트.
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="이미지 파일이 비어 있습니다.")

    try:
        result = await debug_ailab_hairstyle(raw, hair_type=hair_type)
        return result
    except AILabError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"AILab 요청 중 오류: {e}",
        )


# ─────────────────────────────────────────────
# 2. 내부 유틸 함수
# ─────────────────────────────────────────────
def _is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://") or value.startswith(
        "data:"
    )


def _file_to_data_uri(path: str, mime: str = "image/png") -> str:
    with open(path, "rb") as f:
        b = f.read()
    return f"data:{mime};base64," + base64.b64encode(b).decode("utf-8")


def _bytes_to_data_uri(data: bytes, mime: str = "image/jpeg") -> str:
    return f"data:{mime};base64," + base64.b64encode(data).decode("utf-8")


# ─────────────────────────────────────────────
# 3. 단일 2D 합성 테스트용 (선택 사항)
# ─────────────────────────────────────────────
@router.post("/hair")
async def hair_fusion(
    file: UploadFile = File(...),
    hair_type: Optional[int] = Form(None),
):
    """
    AILab 2D 헤어 합성만 단독으로 확인하고 싶을 때 사용하는 엔드포인트.
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="이미지 파일이 비어 있습니다.")

    source_path = save_bytes_to_file(settings.media_root, "source", raw, ".jpg")
    fused_path = await try_ailab_hairstyle(raw, hair_type=hair_type)

    return {
        "status": "ok",
        "source_image_url": source_path,
        "fused_image_url": fused_path,
        "note": "fused_image_url이 있으면 그걸 사용하세요.",
    }


# ─────────────────────────────────────────────
# 4. Meshy 작업 생성 & 상태 조회
# ─────────────────────────────────────────────
@router.post("/meshify")
async def meshify_create(image_url: str = Form(...)):
    """
    수동으로 image_url을 넘겨 Meshy Image-to-3D 작업을 생성.
    (full 파이프라인에서는 내부적으로 사용)
    """
    try:
        task_id = await create_meshy_image_to_3d(image_url)
        return {
            "status": "task_created",
            "task_id": task_id,
            "note": "이 task_id를 /fusion/meshify/{task_id} 로 조회하면 상태와 glb_url 확인 가능.",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Meshy 작업 생성 중 오류: {e}",
        )


@router.get("/meshify/{task_id}")
async def meshify_result(task_id: str):
    """
    Meshy 작업 상태 조회 엔드포인트.
    """
    try:
        task_data = await get_meshy_task(task_id)
        status_value = (task_data.get("status") or "").lower()
        progress = task_data.get("progress")
        glb_url = extract_glb_url(task_data)

        return {
            "status": status_value,
            "task_id": task_id,
            "progress": progress,
            "glb_url": glb_url or None,
            "task": task_data,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Meshy 결과 조회 중 오류: {e}",
        )


# ─────────────────────────────────────────────
# 5. GLB 프록시 (CORS 문제 해결용)
# ─────────────────────────────────────────────
@router.get("/mesh-view")
async def mesh_view(
    glb_url: str = Query(..., description="Meshy에서 받은 glb_url"),
):
    """
    프론트에서 Meshy glb_url을 직접 요청하면 CORS가 걸릴 수 있으므로,
    백엔드가 대신 받아서 같은 Origin으로 반환해주는 프록시.
    """
    decoded_url = unquote(glb_url)

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(decoded_url)

        if resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"원격 GLB 요청 실패 (status={resp.status_code})",
            )

        media_type = resp.headers.get("content-type", "model/gltf-binary")

        return StreamingResponse(
            iter([resp.content]),
            media_type=media_type,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GLB 프록시 중 오류: {e}",
        )


# ─────────────────────────────────────────────
# 6. 전체 자동 파이프라인 (2D 합성 필수 + 3D 생성)
# ─────────────────────────────────────────────
@router.post("/full")
async def full_pipeline_strict(
    file: UploadFile = File(...),
    hair_type: int = Form(...),
):
    """
    [서비스 컨셉용 최종 버전]

    1) 유저 얼굴 사진 업로드
    2) 지정한 hair_type으로 AILab 2D 헤어 합성 (필수)
       - 실패 시 전체 요청을 에러로 반환 (원본으로 3D 생성하지 않음)
    3) 합성된 이미지를 Meshy Image-to-3D에 전달하여 task_id 발급
    4) 프론트는 /fusion/meshify/{task_id} 로 glb_url 확인 후, /fusion/mesh-view 로 조회

    ※ hair_type 은 AILab이 허용하는 값만 사용해야 함:
       101, 201, 301, 401, 402, 403, 502, 503, 603,
       801, 901, 1001, 1101, 1201, 1301
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="이미지 파일이 비어 있습니다.")

    # 1. 원본 저장
    source_path = save_bytes_to_file(settings.media_root, "source", raw, ".jpg")

    # 2. AILab 2D 헤어 합성 (필수)
    try:
        fused_path = await require_ailab_hairstyle(raw, hair_type=hair_type)
    except AILabError as e:
        # 여기서 바로 종료: 2D 합성 안 되면 3D 생성도 안 함
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"2D 헤어 합성 실패: {e}",
        )

    used_image_source = "fused"

    # 3. Meshy에 넘길 입력 (URL 또는 data URI)
    if _is_url(fused_path):
        meshy_input = fused_path
    else:
        meshy_input = _file_to_data_uri(fused_path, mime="image/png")

    # 4. Meshy 작업 생성
    try:
        task_id = await create_meshy_image_to_3d(meshy_input)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Meshy 작업 생성 중 오류: {e}",
        )

    return {
        "status": "task_created",
        "source_image_url": source_path,
        "fused_image_url": fused_path,
        "used_image_source": used_image_source,
        "task_id": task_id,
        "note": "2D 합성된 이미지를 기반으로 3D 생성 작업을 시작했습니다. /fusion/meshify/{task_id} → glb_url → /fusion/mesh-view 로 사용하세요.",
    }
