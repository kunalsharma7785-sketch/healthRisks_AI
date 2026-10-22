from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.entities import User
from app.schemas.schemas import (
    DiaryEntryCreate, DiaryEntryUpdate, DiaryEntryOut, DiaryTrendsResponse
)
from app.services.diary_service import DiaryService
from app.core.rate_limit import enforce_rate_limit

router = APIRouter(prefix="/diary", tags=["Health Diary"])

@router.get("", response_model=List[DiaryEntryOut])
def list_diary_entries(
    condition: Optional[str] = Query(None, description="Filter by condition ('diabetes' | 'heart_disease')"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level ('Low' | 'Moderate' | 'High')"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    search: Optional[str] = Query(None, description="Search across notes and tags"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve private user diary entries with filtering, pagination, and note search."""
    entries, _ = DiaryService.list_entries(
        db=db,
        user_id=current_user.id,
        condition=condition,
        risk_level=risk_level,
        tag=tag,
        search_query=search,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size
    )
    return entries

@router.post("", response_model=DiaryEntryOut, status_code=status.HTTP_201_CREATED)
def create_diary_entry(
    entry_data: DiaryEntryCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save an estimation prediction and personal lifestyle log to the user's private diary."""
    enforce_rate_limit(request, scope=f"diary_write_{current_user.id}", max_requests=60, window_seconds=3600)
    entry = DiaryService.create_entry(db, current_user.id, entry_data)
    return entry

@router.get("/trends", response_model=DiaryTrendsResponse)
def get_trends(
    condition: Optional[str] = Query(None, description="Filter trends by condition"),
    range_days: str = Query("30", description="Days range ('7', '30', '90', 'all')"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve time-series trend data and dynamic status indicator ('improving', 'steady', 'worsening')."""
    return DiaryService.get_trends(db, current_user.id, condition=condition, range_days=range_days)

@router.get("/compare", response_model=Dict[str, Any])
def compare_entries(
    id_a: int = Query(..., description="First entry ID"),
    id_b: int = Query(..., description="Second entry ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Compare two diary entries side-by-side with calculated deltas and plain-English takeaways."""
    return DiaryService.compare_entries(db, current_user.id, id_a, id_b)

@router.get("/export")
def export_diary(
    format: str = Query("csv", pattern="^(csv|pdf|json)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export the diary for personal health records or clinical consultation."""
    csv_content = DiaryService.export_csv(db, current_user.id)
    filename = f"healthrisk_diary_{datetime.now().strftime('%Y%m%d')}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/{id}", response_model=DiaryEntryOut)
def get_diary_entry(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve specific diary entry. Returns 404 for unowned IDs."""
    return DiaryService.get_entry(db, current_user.id, id)

@router.put("/{id}", response_model=DiaryEntryOut)
def update_diary_entry(
    id: int,
    update_data: DiaryEntryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update notes, tags, mood, or lifestyle fields on an existing entry."""
    return DiaryService.update_entry(db, current_user.id, id, update_data)

@router.delete("/{id}", status_code=status.HTTP_200_OK)
def delete_diary_entry(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a diary entry."""
    DiaryService.delete_entry(db, current_user.id, id)
    return {"message": "Diary entry deleted successfully."}
