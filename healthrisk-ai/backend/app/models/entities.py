from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, Index, JSON
)
from sqlalchemy.orm import relationship
from app.core.database import Base

def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_verified = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Cascading relationships
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")
    diary_entries = relationship("DiaryEntry", back_populates="user", cascade="all, delete-orphan")
    goals = relationship("Goal", back_populates="user", cascade="all, delete-orphan")

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    user = relationship("User", back_populates="refresh_tokens")

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    user = relationship("User", back_populates="password_reset_tokens")

class DiaryEntry(Base):
    __tablename__ = "diary_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entry_date = Column(DateTime, default=utc_now, nullable=False, index=True)
    condition = Column(String(50), nullable=False)  # "diabetes" | "heart_disease"
    measurements = Column(JSON, nullable=False)     # {age, bmi, glucose, etc.}
    probability = Column(Float, nullable=False)     # 0.0 to 1.0
    risk_level = Column(String(20), nullable=False) # "Low" | "Moderate" | "High"
    model_version = Column(String(50), nullable=False)
    top_factors = Column(JSON, nullable=False)      # list of {feature, impact, direction, explanation}
    
    # Personal & Lifestyle fields
    note = Column(Text, nullable=True)
    mood = Column(Integer, nullable=True)           # 1 to 5
    tags = Column(JSON, default=list, nullable=False)
    sleep_hours = Column(Float, nullable=True)
    steps = Column(Integer, nullable=True)
    water_intake_ml = Column(Integer, nullable=True)
    medication_taken = Column(Boolean, nullable=True)
    diet_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=utc_now, nullable=False)

    user = relationship("User", back_populates="diary_entries")

    __table_args__ = (
        Index("ix_diary_user_entry_date", "user_id", "entry_date"),
    )

class Goal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    target_metric = Column(String(50), nullable=False)  # "glucose", "bmi", "blood_pressure", etc.
    target_value = Column(Float, nullable=False)
    current_value = Column(Float, nullable=True)
    unit = Column(String(30), nullable=False)
    direction = Column(String(10), default="under", nullable=False) # "under" | "over"
    achieved = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    user = relationship("User", back_populates="goals")
