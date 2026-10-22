from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.entities import User, DiaryEntry, Goal
from app.schemas.schemas import ChangePasswordRequest
from app.services.auth_service import AuthService
from app.core.audit import AuditLogger
from app.core.rate_limit import get_client_ip

router = APIRouter(prefix="/account", tags=["Account Management"])

@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    data: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change account password with current password verification."""
    AuthService.change_password(db, current_user.id, data.current_password, data.new_password, request)
    return {"message": "Password updated successfully."}

@router.get("/export-data")
def export_user_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Data portability: export complete user profile, diary history, and goals in JSON format."""
    entries = db.query(DiaryEntry).filter(DiaryEntry.user_id == current_user.id).all()
    goals = db.query(Goal).filter(Goal.user_id == current_user.id).all()

    return {
        "user_profile": {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "created_at": current_user.created_at.isoformat()
        },
        "diary_entries": [
            {
                "id": e.id,
                "date": e.entry_date.isoformat(),
                "condition": e.condition,
                "measurements": e.measurements,
                "probability": e.probability,
                "risk_level": e.risk_level,
                "model_version": e.model_version,
                "note": e.note,
                "mood": e.mood,
                "tags": e.tags,
                "lifestyle": {
                    "sleep_hours": e.sleep_hours,
                    "steps": e.steps,
                    "water_intake_ml": e.water_intake_ml,
                    "medication_taken": e.medication_taken,
                    "diet_notes": e.diet_notes
                }
            } for e in entries
        ],
        "goals": [
            {
                "id": g.id,
                "title": g.title,
                "metric": g.target_metric,
                "target_value": g.target_value,
                "current_value": g.current_value,
                "unit": g.unit,
                "direction": g.direction,
                "achieved": g.achieved
            } for g in goals
        ],
        "export_timestamp": datetime.now(timezone.utc).isoformat()
    }

@router.delete("", status_code=status.HTTP_200_OK)
def delete_account(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Permanently delete user account and all associated health records (GDPR Right to Erasure)."""
    ip = get_client_ip(request)
    user_id = current_user.id
    email = current_user.email

    db.delete(current_user)
    db.commit()

    AuditLogger.log_event("ACCOUNT_DELETED", "SUCCESS", ip, str(user_id), {"email": email})
    return {"message": "Account and all associated health data have been permanently deleted."}
