"""Health Check Endpoints"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from app.core.config import settings
from app.db.session import get_db
from app.schemas.common import HealthResponse

router = APIRouter()


@router.get("", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """
    Health check endpoint.
    Checks database and Redis connectivity.
    """
    # Check database
    db_status = "connected"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "disconnected"
    
    # Check Redis
    redis_status = "connected"
    try:
        r = redis.from_url(settings.redis_url)
        await r.ping()
        await r.close()
    except Exception:
        redis_status = "disconnected"
    
    return HealthResponse(
        status="healthy" if db_status == "connected" and redis_status == "connected" else "degraded",
        version="1.0.0",
        timestamp=datetime.now(timezone.utc),
        database=db_status,
        redis=redis_status,
    )


@router.get("/ready")
async def readiness_check() -> dict:
    """Kubernetes readiness probe."""
    return {"ready": True}


@router.get("/live")
async def liveness_check() -> dict:
    """Kubernetes liveness probe."""
    return {"alive": True}
