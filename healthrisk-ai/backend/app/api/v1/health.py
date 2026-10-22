from fastapi import APIRouter

router = APIRouter(tags=["System"])

@router.get("/health")
def health_check():
    """Liveness probe. Reveals no internal architecture details for security."""
    return {"status": "ok"}
