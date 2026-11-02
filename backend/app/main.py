from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.config import settings
from app.services.analysis_jobs import analysis_job_worker


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting persistent video analysis worker.")
    analysis_job_worker.start()
    try:
        yield
    finally:
        analysis_job_worker.stop()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Intelligent Road Accident Detection and Emergency Response Platform",
    debug=settings.debug,
    lifespan=lifespan,
)

if settings.cors_allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Range"],
        expose_headers=[
            "Accept-Ranges",
            "Content-Length",
            "Content-Range",
        ],
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