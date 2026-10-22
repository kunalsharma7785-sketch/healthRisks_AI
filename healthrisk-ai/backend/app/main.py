import os
import time
import uuid
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.database import engine, Base
from app.services.ml_service import MLService
from app.api.v1 import auth, predict, diary, goals, account, model, health

# Configure safe structured logging (Never log raw health measurements or secrets)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("healthrisk.app")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables and ML models
    logger.info("Starting up HealthRisk AI Backend...")
    Base.metadata.create_all(bind=engine)
    try:
        MLService.initialize()
    except Exception as e:
        logger.error("Error during ML initialization: %s", e)
    yield
    logger.info("Shutting down HealthRisk AI Backend...")

# Disable /docs in production
docs_url = None if settings.ENVIRONMENT == "production" else "/docs"
redoc_url = None if settings.ENVIRONMENT == "production" else "/redoc"

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Educational screening demo estimating diabetes & heart disease risk from basic health measurements.",
    version="1.0.0",
    docs_url=docs_url,
    redoc_url=redoc_url,
    lifespan=lifespan
)

# 1. Security Headers & Request Tracking Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start_time = time.time()

        # Enforce max body size (1MB max to prevent memory exhaustion / DoS)
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > 1048576:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": "Payload exceeds allowed size limit."}
            )

        try:
            response = await call_next(request)
        except Exception as exc:
            logger.error("Unhandled error [RequestID: %s]: %s", request_id, exc, exc_info=True)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "An internal error occurred. Please try again later."}
            )

        process_time = time.time() - start_time
        # Safe logging: log request ID, method, path, status, and duration only (NO body data or tokens)
        logger.info(
            "req_id=%s method=%s path=%s status=%s duration=%.4fs",
            request_id, request.method, request.url.path, response.status_code, process_time
        )

        # Apply strict security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' data: https:; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "connect-src 'self' http://localhost:* http://127.0.0.1:* ws: wss:;"
        )
        if settings.ENVIRONMENT != "development":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        response.headers["X-Request-ID"] = request_id
        return response

app.add_middleware(SecurityHeadersMiddleware)

# 2. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Retry-After", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-Request-ID"]
)

# 3. Mount Routers
app.include_router(health.router)
app.include_router(predict.router)
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(predict.router, prefix=settings.API_V1_STR)
app.include_router(diary.router, prefix=settings.API_V1_STR)
app.include_router(goals.router, prefix=settings.API_V1_STR)
app.include_router(account.router, prefix=settings.API_V1_STR)
app.include_router(model.router, prefix=settings.API_V1_STR)

# 4. Serve Frontend SPA
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
FRONTEND_DIR = os.environ.get("FRONTEND_DIR", os.path.join(PROJECT_ROOT, "frontend"))
if not os.path.exists(FRONTEND_DIR) and os.path.exists(os.path.join(BACKEND_DIR, "frontend")):
    FRONTEND_DIR = os.path.join(BACKEND_DIR, "frontend")

if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
    
    @app.get("/")
    async def serve_index():
        index_file = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "HealthRisk AI API is running. Visit /docs for OpenAPI specifications."}
