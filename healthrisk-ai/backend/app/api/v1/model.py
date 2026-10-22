from fastapi import APIRouter
from app.services.ml_service import MLService

router = APIRouter(prefix="/model", tags=["Model Information"])

@router.get("/metrics")
def get_model_metrics():
    """
    Return empirical cross-validation metrics (recall, ROC-AUC, precision)
    for Logistic Regression, Random Forest, and Gradient Boosting / XGBoost.
    Includes clinical justification for prioritizing Recall + ROC-AUC over raw Accuracy.
    """
    data = MLService.get_metrics()
    return {
        "status": "success",
        "rationale": "In clinical screening, Recall (minimizing false negatives) and ROC-AUC are prioritized above raw Accuracy to ensure high-risk individuals are not missed.",
        "metrics": data
    }
