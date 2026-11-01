from fastapi import FastAPI

from app.api.v1.router import api_router
from app.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Intelligent Road Accident Detection and Emergency Response Platform",
    debug=settings.debug,
)

app.include_router(
    api_router,
    prefix=settings.api_v1_prefix,
)


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Welcome to CrashSense API",
        "status": "running",
        "docs": "/docs",
    }