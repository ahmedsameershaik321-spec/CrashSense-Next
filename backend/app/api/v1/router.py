from fastapi import APIRouter

from app.api.v1.endpoints import admin, auth, cameras, health, operator, videos

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(operator.router)
api_router.include_router(admin.router)
api_router.include_router(cameras.router)
api_router.include_router(videos.router)