from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.entities import User, Goal
from app.schemas.schemas import GoalCreate, GoalOut

router = APIRouter(prefix="/goals", tags=["Health Goals"])

@router.get("", response_model=List[GoalOut])
def list_goals(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List private personal lifestyle goals for the current user."""
    return db.query(Goal).filter(Goal.user_id == current_user.id).all()

@router.post("", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
def create_goal(
    goal_data: GoalCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a personal health habit tracking goal.
    Note: These are personal habit milestones and never medical prescriptions.
    """
    goal = Goal(
        user_id=current_user.id,
        title=goal_data.title.strip(),
        target_metric=goal_data.target_metric,
        target_value=goal_data.target_value,
        unit=goal_data.unit.strip(),
        direction=goal_data.direction,
        achieved=False
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal

@router.delete("/{id}", status_code=status.HTTP_200_OK)
def delete_goal(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a goal. Returns 404 for unowned IDs."""
    goal = db.query(Goal).filter(Goal.id == id, Goal.user_id == current_user.id).first()
    if not goal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found.")
    db.delete(goal)
    db.commit()
    return {"message": "Goal removed successfully."}
