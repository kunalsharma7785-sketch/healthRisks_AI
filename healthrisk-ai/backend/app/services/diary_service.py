import io
import csv
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from fastapi import HTTPException, status

from app.models.entities import DiaryEntry, Goal
from app.schemas.schemas import (
    DiaryEntryCreate, DiaryEntryUpdate, DiaryEntryOut, DiaryTrendsResponse, TrendPoint
)
from app.core.security import sanitize_text, sanitize_tags

class DiaryService:

    @staticmethod
    def create_entry(db: Session, user_id: int, data: DiaryEntryCreate) -> DiaryEntry:
        clean_note = sanitize_text(data.note, max_length=2000)
        clean_tags = sanitize_tags(data.tags)
        clean_diet = sanitize_text(data.diet_notes, max_length=1000)

        entry_date = data.entry_date
        if entry_date:
            entry_date = entry_date.replace(tzinfo=None)
        else:
            entry_date = datetime.now(timezone.utc).replace(tzinfo=None)

        # Convert measurements and factors to dict for JSON storage
        meas_dict = data.measurements.model_dump()
        top_factors_list = [f.model_dump() for f in data.top_factors]

        entry = DiaryEntry(
            user_id=user_id,
            entry_date=entry_date,
            condition=data.condition,
            measurements=meas_dict,
            probability=data.probability,
            risk_level=data.risk_level,
            model_version=data.model_version,
            top_factors=top_factors_list,
            note=clean_note,
            mood=data.mood,
            tags=clean_tags,
            sleep_hours=data.sleep_hours,
            steps=data.steps,
            water_intake_ml=data.water_intake_ml,
            medication_taken=data.medication_taken,
            diet_notes=clean_diet
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        # Check goals updates
        DiaryService.update_goals_with_entry(db, user_id, entry)

        return entry

    @staticmethod
    def list_entries(
        db: Session,
        user_id: int,
        condition: Optional[str] = None,
        risk_level: Optional[str] = None,
        tag: Optional[str] = None,
        search_query: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[DiaryEntry], int]:
        query = db.query(DiaryEntry).filter(DiaryEntry.user_id == user_id)

        if condition:
            query = query.filter(DiaryEntry.condition == condition)
        if risk_level:
            query = query.filter(DiaryEntry.risk_level == risk_level)
        if start_date:
            query = query.filter(DiaryEntry.entry_date >= start_date)
        if end_date:
            query = query.filter(DiaryEntry.entry_date <= end_date)

        entries = query.order_by(desc(DiaryEntry.entry_date)).all()

        # In-memory post filtering for JSON fields (tag and search note)
        filtered = []
        for e in entries:
            if tag and tag not in (e.tags or []):
                continue
            if search_query:
                q = search_query.lower()
                note_match = (e.note and q in e.note.lower())
                tag_match = any(q in t.lower() for t in (e.tags or []))
                if not (note_match or tag_match):
                    continue
            filtered.append(e)

        total_count = len(filtered)
        start_idx = (page - 1) * page_size
        paginated = filtered[start_idx : start_idx + page_size]

        return paginated, total_count

    @staticmethod
    def get_entry(db: Session, user_id: int, entry_id: int) -> DiaryEntry:
        # Return 404 (not 403) for other users' IDs to prevent ID enumeration
        entry = db.query(DiaryEntry).filter(
            DiaryEntry.id == entry_id,
            DiaryEntry.user_id == user_id
        ).first()
        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diary entry not found.")
        return entry

    @staticmethod
    def update_entry(db: Session, user_id: int, entry_id: int, data: DiaryEntryUpdate) -> DiaryEntry:
        entry = DiaryService.get_entry(db, user_id, entry_id)

        if data.note is not None:
            entry.note = sanitize_text(data.note, max_length=2000)
        if data.mood is not None:
            entry.mood = data.mood
        if data.tags is not None:
            entry.tags = sanitize_tags(data.tags)
        if data.sleep_hours is not None:
            entry.sleep_hours = data.sleep_hours
        if data.steps is not None:
            entry.steps = data.steps
        if data.water_intake_ml is not None:
            entry.water_intake_ml = data.water_intake_ml
        if data.medication_taken is not None:
            entry.medication_taken = data.medication_taken
        if data.diet_notes is not None:
            entry.diet_notes = sanitize_text(data.diet_notes, max_length=1000)

        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def delete_entry(db: Session, user_id: int, entry_id: int):
        entry = DiaryService.get_entry(db, user_id, entry_id)
        db.delete(entry)
        db.commit()

    @staticmethod
    def get_trends(
        db: Session,
        user_id: int,
        condition: Optional[str] = None,
        range_days: str = "30"
    ) -> DiaryTrendsResponse:
        query = db.query(DiaryEntry).filter(DiaryEntry.user_id == user_id)
        if condition:
            query = query.filter(DiaryEntry.condition == condition)

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if range_days != "all":
            try:
                days = int(range_days)
                cutoff = now - timedelta(days=days)
                query = query.filter(DiaryEntry.entry_date >= cutoff)
            except ValueError:
                pass

        entries = query.order_by(DiaryEntry.entry_date.asc()).all()

        points: List[TrendPoint] = []
        for e in entries:
            meas = e.measurements or {}
            points.append(TrendPoint(
                date=e.entry_date.strftime("%b %d"),
                timestamp=e.entry_date.isoformat(),
                probability=round(e.probability * 100, 1),
                glucose=float(meas.get("glucose", 0)),
                bmi=float(meas.get("bmi", 0)),
                blood_pressure=float(meas.get("blood_pressure", 0)),
                cholesterol=float(meas.get("cholesterol", 0)),
                risk_level=e.risk_level
            ))

        if len(points) == 0:
            return DiaryTrendsResponse(
                condition_filter=condition,
                range_days=range_days,
                points=[],
                latest_risk=None,
                change_from_previous=None,
                status_indicator="insufficient_data"
            )

        latest_risk = points[-1].probability
        change_from_previous = None
        status_ind = "steady"

        if len(points) >= 2:
            prev_risk = points[-2].probability
            change_from_previous = round(latest_risk - prev_risk, 1)
            if change_from_previous <= -2.0:
                status_ind = "improving"
            elif change_from_previous >= 2.0:
                status_ind = "worsening"
            else:
                status_ind = "steady"

        return DiaryTrendsResponse(
            condition_filter=condition,
            range_days=range_days,
            points=points,
            latest_risk=latest_risk,
            change_from_previous=change_from_previous,
            status_indicator=status_ind
        )

    @staticmethod
    def compare_entries(db: Session, user_id: int, id_a: int, id_b: int) -> Dict[str, Any]:
        entry_a = DiaryService.get_entry(db, user_id, id_a)
        entry_b = DiaryService.get_entry(db, user_id, id_b)

        # Sort chronological (older first)
        if entry_a.entry_date > entry_b.entry_date:
            older, newer = entry_b, entry_a
        else:
            older, newer = entry_a, entry_b

        diffs = {}
        for metric in ["glucose", "blood_pressure", "bmi", "cholesterol"]:
            val_old = older.measurements.get(metric)
            val_new = newer.measurements.get(metric)
            if val_old is not None and val_new is not None:
                diffs[metric] = {
                    "older": val_old,
                    "newer": val_new,
                    "change": round(val_new - val_old, 1)
                }

        prob_old_pct = round(older.probability * 100, 1)
        prob_new_pct = round(newer.probability * 100, 1)
        prob_change = round(prob_new_pct - prob_old_pct, 1)

        # Generate friendly plain-English takeaway
        takeaways = []
        if "glucose" in diffs:
            g_change = diffs["glucose"]["change"]
            if g_change < 0:
                takeaways.append(f"Glucose decreased by {abs(g_change)} mg/dL")
            elif g_change > 0:
                takeaways.append(f"Glucose increased by {g_change} mg/dL")

        if prob_change < 0:
            takeaways.append(f"estimated risk lowered from {prob_old_pct}% to {prob_new_pct}%")
        elif prob_change > 0:
            takeaways.append(f"estimated risk shifted from {prob_old_pct}% to {prob_new_pct}%")
        else:
            takeaways.append(f"estimated risk remained stable at {prob_new_pct}%")

        summary_sentence = ", ".join(takeaways).capitalize() + "." if takeaways else "Measurements compared."

        return {
            "older_entry": DiaryEntryOut.model_validate(older).model_dump(),
            "newer_entry": DiaryEntryOut.model_validate(newer).model_dump(),
            "metric_differences": diffs,
            "risk_change": {
                "older_risk": prob_old_pct,
                "newer_risk": prob_new_pct,
                "delta": prob_change
            },
            "plain_english_summary": summary_sentence
        }

    @staticmethod
    def export_csv(db: Session, user_id: int) -> str:
        entries = db.query(DiaryEntry).filter(
            DiaryEntry.user_id == user_id
        ).order_by(DiaryEntry.entry_date.desc()).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID", "Date", "Condition", "Estimated Risk (%)", "Risk Level",
            "Age", "Sex", "BMI", "Blood Pressure (mm Hg)", "Glucose (mg/dL)", "Cholesterol (mg/dL)",
            "Mood (1-5)", "Tags", "Sleep Hours", "Steps", "Water (ml)", "Notes", "Model Version"
        ])

        for e in entries:
            m = e.measurements or {}
            writer.writerow([
                e.id,
                e.entry_date.strftime("%Y-%m-%d %H:%M"),
                e.condition,
                round(e.probability * 100, 1),
                e.risk_level,
                m.get("age", ""),
                "Male" if m.get("sex") == 1 else "Female",
                m.get("bmi", ""),
                m.get("blood_pressure", ""),
                m.get("glucose", ""),
                m.get("cholesterol", ""),
                e.mood or "",
                ", ".join(e.tags or []),
                e.sleep_hours or "",
                e.steps or "",
                e.water_intake_ml or "",
                e.note or "",
                e.model_version
            ])

        return output.getvalue()

    @staticmethod
    def update_goals_with_entry(db: Session, user_id: int, entry: DiaryEntry):
        meas = entry.measurements or {}
        goals = db.query(Goal).filter(Goal.user_id == user_id).all()
        for g in goals:
            val = None
            if g.target_metric in meas:
                val = float(meas[g.target_metric])
            elif g.target_metric == "steps" and entry.steps:
                val = float(entry.steps)
            elif g.target_metric == "sleep_hours" and entry.sleep_hours:
                val = float(entry.sleep_hours)

            if val is not None:
                g.current_value = val
                if g.direction == "under":
                    g.achieved = (val <= g.target_value)
                else:
                    g.achieved = (val >= g.target_value)
        db.commit()
