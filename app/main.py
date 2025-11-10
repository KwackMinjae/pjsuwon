from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import fusion as fusion_router
from app.routes import uploads as uploads_router
from app.settings import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="HairFusion Service",
        version="0.1.0",
    )

    # CORS 설정 (프론트에서 다른 포트/도메인에서 호출 가능하도록)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],          # 개발 단계: 전체 허용
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 라우터 등록
    app.include_router(fusion_router.router)
    app.include_router(uploads_router.router)

    @app.get("/health")
    async def health_check():
        return {
            "status": "ok",
            "meshy_configured": bool(settings.meshy_api_key),
            "ailab_configured": bool(settings.ailab_api_key),
        }

    return app


app = create_app()
