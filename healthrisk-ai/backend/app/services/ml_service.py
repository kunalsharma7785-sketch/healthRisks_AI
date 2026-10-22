import os
import json
import hashlib
import logging
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
import joblib

from app.core.config import settings
from app.schemas.schemas import HealthMeasurements, ContributingFactor, PredictionResponse

logger = logging.getLogger("healthrisk.ml")

HUMAN_FEATURE_NAMES = {
    "age": "Age",
    "sex": "Sex",
    "bmi": "Body Mass Index (BMI)",
    "blood_pressure": "Resting Blood Pressure",
    "glucose": "Blood Glucose Level",
    "cholesterol": "Serum Cholesterol",
    "pregnancies": "Pregnancy History",
    "insulin": "Serum Insulin",
    "chest_pain_type": "Chest Pain Pattern",
    "max_heart_rate": "Peak Exercise Heart Rate"
}

FEATURE_UNITS = {
    "age": "years",
    "sex": "",
    "bmi": "kg/m²",
    "blood_pressure": "mm Hg",
    "glucose": "mg/dL",
    "cholesterol": "mg/dL",
    "pregnancies": "",
    "insulin": "µU/mL",
    "chest_pain_type": "",
    "max_heart_rate": "bpm"
}

class MLService:
    _models: Dict[str, Any] = {}
    _metadata: Dict[str, Any] = {}
    _initialized: bool = False

    @classmethod
    def initialize(cls):
        """Load and verify ML pipelines at application startup."""
        if cls._initialized:
            return

        model_dir = settings.MODEL_DIR
        checksum_file = os.path.join(model_dir, "checksums.json")

        if not os.path.exists(checksum_file):
            logger.warning("Checksum file not found at %s. Attempting to run training script.", checksum_file)
            try:
                from ml_models.train_models import main as train_main
                train_main()
            except Exception as e:
                logger.error("Failed to train models dynamically: %s", e)

        with open(checksum_file, "r") as f:
            expected_checksums = json.load(f)

        for condition, filename in [("diabetes", "diabetes_pipeline.joblib"), ("heart_disease", "heart_pipeline.joblib")]:
            model_path = os.path.join(model_dir, filename)
            meta_path = os.path.join(model_dir, f"{condition.split('_')[0]}_meta.json")

            if not os.path.exists(model_path):
                raise RuntimeError(f"Missing model artifact: {model_path}")

            # Verify cryptographic SHA-256 integrity
            with open(model_path, "rb") as f:
                content = f.read()
                actual_hash = hashlib.sha256(content).hexdigest()
                expected_hash = expected_checksums.get(filename)
                if expected_hash and actual_hash != expected_hash:
                    raise SecurityError(f"Model integrity checksum mismatch for {filename}!")

            cls._models[condition] = joblib.load(model_path)

            if os.path.exists(meta_path):
                with open(meta_path, "r") as f:
                    cls._metadata[condition] = json.load(f)

        cls._initialized = True
        logger.info("HealthRisk AI ML pipelines initialized and verified successfully.")

    @classmethod
    def get_metrics(cls) -> Dict[str, Any]:
        """Return model evaluation metrics (recall, ROC-AUC, precision) and comparison data."""
        return {
            "diabetes": cls._metadata.get("diabetes", {}).get("metrics", {}),
            "heart_disease": cls._metadata.get("heart_disease", {}).get("metrics", {}),
            "metadata": {
                "diabetes": {
                    "dataset": cls._metadata.get("diabetes", {}).get("dataset_name", "Pima Indians Diabetes"),
                    "sample_size": cls._metadata.get("diabetes", {}).get("sample_size", 768),
                    "selected_model": cls._metadata.get("diabetes", {}).get("best_model", "Random Forest"),
                    "version": cls._metadata.get("diabetes", {}).get("version", "1.0.0")
                },
                "heart_disease": {
                    "dataset": cls._metadata.get("heart_disease", {}).get("dataset_name", "Cleveland Heart Disease"),
                    "sample_size": cls._metadata.get("heart_disease", {}).get("sample_size", 303),
                    "selected_model": cls._metadata.get("heart_disease", {}).get("best_model", "Logistic Regression"),
                    "version": cls._metadata.get("heart_disease", {}).get("version", "1.0.0")
                }
            }
        }

    @classmethod
    def check_dangerous_ranges(cls, measurements: HealthMeasurements) -> Optional[str]:
        """Check for critical physiological outliers requiring medical consultation."""
        alerts = []
        if measurements.glucose >= 300:
            alerts.append(f"A blood glucose level of {measurements.glucose} mg/dL is notably elevated.")
        elif measurements.glucose < 54:
            alerts.append(f"A blood glucose level of {measurements.glucose} mg/dL indicates significant hypoglycemia.")

        if measurements.blood_pressure >= 180:
            alerts.append(f"A resting blood pressure of {measurements.blood_pressure} mm Hg is in the hypertensive crisis tier.")
        elif measurements.blood_pressure < 70:
            alerts.append(f"A resting blood pressure of {measurements.blood_pressure} mm Hg indicates severe hypotension.")

        if measurements.max_heart_rate and measurements.max_heart_rate > 215:
            alerts.append(f"A heart rate of {measurements.max_heart_rate} bpm is abnormally elevated.")

        if alerts:
            return (
                "Notice: One or more measurements you entered are outside standard reference ranges ("
                + " ".join(alerts)
                + "). We gently suggest discussing these findings with a qualified healthcare professional promptly."
            )
        return None

    @classmethod
    def predict(cls, condition: str, measurements: HealthMeasurements) -> PredictionResponse:
        """Execute calibrated prediction and calculate SHAP-style factor attributions."""
        if not cls._initialized:
            cls.initialize()

        pipeline = cls._models.get(condition)
        meta = cls._metadata.get(condition, {})

        if not pipeline:
            raise ValueError(f"Unsupported condition: {condition}")

        features = meta.get("features", [])
        medians = meta.get("medians", {})
        weights = meta.get("weights", {})
        model_version = meta.get("version", "1.0.0")

        # Map measurements to DataFrame matching pipeline training columns
        meas_dict = measurements.model_dump()
        input_data = {}
        for feat in features:
            val = meas_dict.get(feat, medians.get(feat, 0))
            # Treat physiological 0 as NaN for imputer
            if feat in ["glucose", "blood_pressure", "bmi", "insulin", "cholesterol"] and val == 0:
                input_data[feat] = [np.nan]
            else:
                input_data[feat] = [float(val)]

        df_input = pd.DataFrame(input_data)

        # Predict probability
        prob_arr = pipeline.predict_proba(df_input)
        raw_prob = float(prob_arr[0][1])
        # Smooth bounds
        probability = round(float(np.clip(raw_prob, 0.02, 0.98)), 3)

        # Risk level determination
        if probability < 0.30:
            risk_level = "Low"
        elif probability < 0.65:
            risk_level = "Moderate"
        else:
            risk_level = "High"

        # Calculate SHAP-like localized feature attributions
        # For each feature: compute normalized deviation from population baseline weighted by model impact
        factors: List[ContributingFactor] = []
        for feat in features:
            entered_val = float(meas_dict.get(feat, 0))
            baseline_val = float(medians.get(feat, entered_val))
            feature_weight = float(weights.get(feat, 0.1))

            # Physiological direction logic
            diff = entered_val - baseline_val
            # In heart disease, high max_heart_rate generally indicates cardiovascular reserve (lowers risk)
            if feat == "max_heart_rate":
                diff = -diff

            impact_val = abs(diff) * feature_weight
            direction = "raises_risk" if diff > 0 else "lowers_risk"

            unit = FEATURE_UNITS.get(feat, "")
            unit_str = f" {unit}" if unit else ""
            human_name = HUMAN_FEATURE_NAMES.get(feat, feat.replace("_", " ").title())

            if direction == "raises_risk":
                if diff == 0:
                    explanation = f"{human_name} ({entered_val}{unit_str}) is near the population baseline."
                else:
                    explanation = f"{human_name} of {entered_val:.0f}{unit_str} pushed your estimated risk up."
            else:
                explanation = f"{human_name} of {entered_val:.0f}{unit_str} helped keep your estimated risk lower."

            factors.append(ContributingFactor(
                feature=human_name,
                raw_feature=feat,
                value=round(entered_val, 1),
                impact=round(float(impact_val), 3),
                direction=direction,
                explanation=explanation
            ))

        # Sort by absolute impact and take top 5
        factors.sort(key=lambda x: x.impact, reverse=True)
        top_5 = factors[:5]

        # Normalize relative impact percentages for clean horizontal bar charts
        total_impact = sum(f.impact for f in top_5) or 1.0
        for f in top_5:
            f.impact = round((f.impact / total_impact) * 100, 1)

        dangerous_warning = cls.check_dangerous_ranges(measurements)

        disclaimer = (
            "This is an educational estimate for learning purposes and not a medical diagnosis. "
            "Always consult a qualified healthcare provider for personal clinical advice. "
            "Entered measurements are not saved anywhere unless you explicitly choose to save them to your private Health Diary."
        )

        return PredictionResponse(
            condition=condition,
            probability=probability,
            risk_level=risk_level,
            model_version=model_version,
            top_factors=top_5,
            disclaimer=disclaimer,
            dangerous_range_warning=dangerous_warning
        )
