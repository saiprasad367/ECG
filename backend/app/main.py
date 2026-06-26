from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from prometheus_fastapi_instrumentator import Instrumentator
import logging

from app.config import settings
from app.database.mongodb import connect_db, close_db
from app.database.redis_client import connect_redis, close_redis
from app.storage.minio_client import ensure_bucket
from app.ml.model_loader import load_model

# Routers
from app.api.routes import session, upload, inference, hex, fpga, analytics, websocket, model

logging.basicConfig(level=logging.INFO if settings.DEBUG else logging.WARNING)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="CardioFPGA Backend API",
        version="1.0.0",
        description="ECG analysis and FPGA validation platform",
    )

    # Middleware — open CORS for all origins (required for Vercel <-> Render cross-origin)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Include routers
    v1 = "/api/v1"
    app.include_router(session.router, prefix=v1)
    app.include_router(upload.router, prefix=v1)
    app.include_router(inference.router, prefix=v1)
    app.include_router(hex.router, prefix=v1)
    app.include_router(hex.hex_router, prefix=v1)
    app.include_router(hex.download_router, prefix=v1)
    app.include_router(fpga.router, prefix=v1)
    app.include_router(analytics.router, prefix=v1)
    app.include_router(websocket.router)
    app.include_router(model.router, prefix=v1)

    # Prometheus monitoring
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    @app.on_event("startup")
    async def startup_event():
        logger.info("🚀 Starting CardioFPGA Backend (Docker-Free Mode)...")
        await connect_db()
        await connect_redis()
        await ensure_bucket()
        try:
            load_model()  # Pre-load ML model into memory
        except Exception as e:
            logger.error(f"❌ Failed to pre-load ML model: {e}")

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("🛑 Shutting down CardioFPGA Backend...")
        await close_db()
        await close_redis()

    @app.get("/", tags=["System"])
    async def root():
        return {"status": "CardioFPGA Backend is running", "version": "1.0.0"}

    @app.get("/health", tags=["System"])
    async def health_check():
        from app.ml.model_loader import model_is_loaded
        return {
            "status": "ok",
            "model_loaded": model_is_loaded(),
            "services": {
                "mongodb": "in-memory (no docker)",
                "redis": "in-memory (no docker)",
                "minio": "filesystem (no docker)",
            }
        }

    return app


app = create_app()
