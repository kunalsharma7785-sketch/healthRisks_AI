from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

class StrictSchema(BaseModel):
    model_config = {
        "extra": "forbid",
        "from_attributes": True
    }

# ==================== AUTH SCHEMAS ====================

EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"

class RegisterRequest(StrictSchema):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., pattern=EMAIL_REGEX)
    password: str = Field(..., min_length=12, max_length=128)
    confirm_password: str = Field(..., min_length=12, max_length=128)
    terms_accepted: bool = Field(...)

    @model_validator(mode="after")
    def check_passwords_and_terms(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        if not self.terms_accepted:
            raise ValueError("You must acknowledge the educational disclaimer and privacy policy to register.")
        return self

class LoginRequest(StrictSchema):
    email: str = Field(..., pattern=EMAIL_REGEX)
    password: str = Field(..., min_length=1, max_length=128)
    remember_me: bool = False

class ForgotPasswordRequest(StrictSchema):
    email: str = Field(..., pattern=EMAIL_REGEX)

class ResetPasswordRequest(StrictSchema):
    token: str = Field(..., min_length=10)
    new_password: str = Field(..., min_length=12, max_length=128)
    confirm_password: str = Field(..., min_length=12, max_length=128)

    @model_validator(mode="after")
    def check_passwords(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self

class ChangePasswordRequest(StrictSchema):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=12, max_length=128)
    confirm_password: str = Field(..., min_length=12, max_length=128)

    @model_validator(mode="after")
    def check_passwords(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self

class UserOut(StrictSchema):
    id: int
    email: str
    full_name: str
    is_verified: bool
    created_at: datetime

class TokenResponse(StrictSchema):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

# ==================== PREDICTION SCHEMAS ====================

class HealthMeasurements(StrictSchema):
    age: int = Field(..., ge=1, le=120, description="Age in years (1-120)")
    sex: int = Field(..., ge=0, le=1, description="Sex: 0 = Female, 1 = Male")
    bmi: float = Field(..., ge=10.0, le=80.0, description="Body Mass Index (kg/m²)")
    blood_pressure: float = Field(..., ge=40.0, le=250.0, description="Resting Blood Pressure (mm Hg)")
    glucose: float = Field(..., ge=20.0, le=600.0, description="Fasting Blood Glucose (mg/dL)")
    cholesterol: float = Field(..., ge=50.0, le=600.0, description="Serum Cholesterol (mg/dL)")
    
    # Diabetes specific
    pregnancies: Optional[int] = Field(0, ge=0, le=20, description="Number of pregnancies (0-20)")
    insulin: Optional[float] = Field(0.0, ge=0.0, le=900.0, description="2-Hour Serum Insulin (mu U/ml)")
    
    # Heart disease specific
    chest_pain_type: Optional[int] = Field(0, ge=0, le=3, description="Chest pain type: 0=typical, 1=atypical, 2=non-anginal, 3=asymptomatic")
    max_heart_rate: Optional[float] = Field(150.0, ge=40.0, le=250.0, description="Maximum heart rate achieved (bpm)")

class PredictionRequest(StrictSchema):
    condition: Literal["diabetes", "heart_disease"]
    measurements: HealthMeasurements

class ContributingFactor(StrictSchema):
    feature: str
    raw_feature: str
    value: float
    impact: float
    direction: Literal["raises_risk", "lowers_risk"]
    explanation: str

class PredictionResponse(StrictSchema):
    condition: str
    probability: float = Field(..., ge=0.0, le=1.0)
    risk_level: Literal["Low", "Moderate", "High"]
    model_version: str
    top_factors: List[ContributingFactor]
    disclaimer: str
    dangerous_range_warning: Optional[str] = None

# ==================== DIARY SCHEMAS ====================

class DiaryEntryCreate(StrictSchema):
    entry_date: Optional[datetime] = None
    condition: Literal["diabetes", "heart_disease"]
    measurements: HealthMeasurements
    probability: float = Field(..., ge=0.0, le=1.0)
    risk_level: Literal["Low", "Moderate", "High"]
    model_version: str
    top_factors: List[ContributingFactor]
    note: Optional[str] = Field(None, max_length=2000)
    mood: Optional[int] = Field(None, ge=1, le=5)
    tags: Optional[List[str]] = Field(default_factory=list)
    sleep_hours: Optional[float] = Field(None, ge=0.0, le=24.0)
    steps: Optional[int] = Field(None, ge=0, le=100000)
    water_intake_ml: Optional[int] = Field(None, ge=0, le=10000)
    medication_taken: Optional[bool] = None
    diet_notes: Optional[str] = Field(None, max_length=1000)

class DiaryEntryUpdate(StrictSchema):
    note: Optional[str] = Field(None, max_length=2000)
    mood: Optional[int] = Field(None, ge=1, le=5)
    tags: Optional[List[str]] = None
    sleep_hours: Optional[float] = Field(None, ge=0.0, le=24.0)
    steps: Optional[int] = Field(None, ge=0, le=100000)
    water_intake_ml: Optional[int] = Field(None, ge=0, le=10000)
    medication_taken: Optional[bool] = None
    diet_notes: Optional[str] = Field(None, max_length=1000)

class DiaryEntryOut(StrictSchema):
    id: int
    user_id: int
    entry_date: datetime
    condition: str
    measurements: Dict[str, Any]
    probability: float
    risk_level: str
    model_version: str
    top_factors: List[Dict[str, Any]]
    note: Optional[str] = None
    mood: Optional[int] = None
    tags: List[str] = []
    sleep_hours: Optional[float] = None
    steps: Optional[int] = None
    water_intake_ml: Optional[int] = None
    medication_taken: Optional[bool] = None
    diet_notes: Optional[str] = None
    created_at: datetime

class TrendPoint(StrictSchema):
    date: str
    timestamp: str
    probability: float
    glucose: float
    bmi: float
    blood_pressure: float
    cholesterol: float
    risk_level: str

class DiaryTrendsResponse(StrictSchema):
    condition_filter: Optional[str] = None
    range_days: str
    points: List[TrendPoint]
    latest_risk: Optional[float] = None
    change_from_previous: Optional[float] = None
    status_indicator: Literal["improving", "steady", "worsening", "insufficient_data"]

# ==================== GOAL SCHEMAS ====================

class GoalCreate(StrictSchema):
    title: str = Field(..., min_length=2, max_length=100)
    target_metric: Literal["glucose", "bmi", "blood_pressure", "cholesterol", "steps", "sleep_hours"]
    target_value: float = Field(..., gt=0)
    unit: str = Field(..., max_length=20)
    direction: Literal["under", "over"] = "under"

class GoalOut(StrictSchema):
    id: int
    user_id: int
    title: str
    target_metric: str
    target_value: float
    current_value: Optional[float] = None
    unit: str
    direction: str
    achieved: bool
    created_at: datetime
