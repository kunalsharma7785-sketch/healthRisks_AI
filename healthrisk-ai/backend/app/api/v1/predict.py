from fastapi import APIRouter, Request, Depends
from app.schemas.schemas import PredictionRequest, PredictionResponse
from app.services.ml_service import MLService
from app.core.rate_limit import enforce_rate_limit
from app.api.deps import get_optional_current_user
from app.models.entities import User
from typing import Optional

router = APIRouter(tags=["Prediction"])

@router.post("/predict", response_model=PredictionResponse)
def predict_health_risk(
    payload: PredictionRequest,
    request: Request,
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Estimate risk probability for diabetes or heart disease with SHAP-based factor attributions.
    Accessible anonymously or with user session.
    Rate limited to 30 requests per minute per IP.
    """
    enforce_rate_limit(request, scope="predict", max_requests=30, window_seconds=60)
    response = MLService.predict(payload.condition, payload.measurements)
    return response
