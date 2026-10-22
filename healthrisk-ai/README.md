# HealthRisk AI 🩺

An educational machine-learning screening web application that estimates an individual's statistical risk for diabetes or heart disease from basic clinical measurements, explains the contributing factors with SHAP-style attributions, and provides a private Health Diary with long-term trend tracking.

> **Notice:** HealthRisk AI is an educational demonstration designed for hackathons, students, and learning. It is **not** a clinical diagnostic tool or medical device.

---

## 🌟 Key Features

### A. Public Landing Page & Risk Checker
- **Usable without an account:** Instant risk calculations with no signup required.
- **Dual Condition Screening:**
  - **Diabetes:** Age, Sex, BMI, Blood Pressure, Glucose, Cholesterol, Pregnancies, Insulin (Pima Indians Diabetes reference model).
  - **Heart Disease:** Age, Sex, BMI, Blood Pressure, Glucose, Cholesterol, Chest Pain Type, Max Heart Rate (Cleveland Heart Disease reference model).
- **Inline Validation & Sample Presets:** Quick buttons to load Low, Moderate, and High-risk sample benchmarks.
- **Results Panel:**
  - Animated radial probability meter (0–100%) with color-coded risk badge (Low / Moderate / High).
  - **"Why this result" SHAP Explanations:** Horizontal bar chart of top 5 contributing factors (warm colors raise risk, cool colors lower risk) with plain-English insights (e.g., *"Blood Glucose Level of 165 mg/dL pushed your estimated risk up"*).
  - **Clinical Outlier Alert:** Calm advisory warning when values enter critical ranges (e.g., Blood Pressure ≥ 180 mm Hg or Glucose ≥ 300 mg/dL).
  - **Actionable Next Steps:** Lifestyle tips and physician guidance.

### B. User Authentication & Security Hardening
- **Argon2id Password Hashing:** Memory-hard password protection resistant to GPU attacks.
- **Brute-Force Lockout:** Progressive lockout after 5 consecutive failures (15 minutes initial lockout, doubling on repeats) with live countdown timer.
- **Generic Security Errors:** Identical response and timing for incorrect passwords vs unknown emails to eliminate enumeration.
- **Secure Token Rotation:** Short-lived JWT access tokens (15 mins) and rotating refresh tokens (7–30 days) stored hashed with SHA-256 in HttpOnly, SameSite=Lax cookies.
- **XSS & SQL Injection Defense:** Parameterized ORM queries, strict Pydantic v2 schemas (`extra="forbid"`, range checks), and HTML sanitization of notes and tags.
- **Audit Logging:** Structured JSON audit trail for logins, failed attempts, lockouts, password resets, and account purges.

### C. Private Health Diary (Signed-in Users)
- **Save Predictions:** One-click save directly from the results panel or manual new entry.
- **Personal Logging:** Mood & energy score (1–5), searchable tags (e.g., `#fasting`, `#post-workout`), sleep hours, daily steps count, and lifestyle notes.
- **Timeline & Filters:** Filter entries by condition, risk tier, tag, or note keyword.
- **Side-by-Side Comparison:** Compare any two entries with calculated biomarker deltas and plain-English summaries (e.g., *"Glucose decreased by 18 mg/dL, estimated risk lowered from 72% to 55%"*).
- **Interactive Trend Charts:** Time-series SVG curves for probability, glucose, blood pressure, BMI, and cholesterol over 7, 30, 90 days, or all time, with an overall trajectory indicator (Improving / Steady / Increasing).
- **Goals Tracking:** Set wellness habit milestones (e.g., *"Keep fasting glucose under 100 mg/dL"*) with live progress bars.
- **Data Portability & Right to Erasure (GDPR):** Export diary as CSV or download full JSON archive; permanent account deletion cascades all records.

---

## 🛠️ Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | Vanilla HTML5, Vanilla CSS3 (Custom Properties Design System, Dark/Light Mode), Modern ES6+ JavaScript, SVG Charting Engine |
| **Backend** | Python 3.11+, FastAPI, SQLAlchemy 2.0 ORM, Pydantic v2, PyJWT, Argon2-CFFI, Redis (with in-memory fallback) |
| **Machine Learning** | Scikit-learn, Random Forest, Logistic Regression, Gradient Boosting, SHAP-style additive feature attributions, Joblib, SHA-256 integrity checksum verification |
| **Testing** | Pytest, Pytest-Asyncio, HTTPX TestClient (100% passing test suite) |
| **DevOps** | Docker, Docker Compose, PostgreSQL 15, Redis 7 |

---

## 🚀 Quick Start & Local Execution

### Option 1: Direct Python & FastAPI Execution (Recommended for Fast Local Testing)

1. **Navigate to the backend directory:**
   ```bash
   cd backend
   ```

2. **Train models and generate checksums (already pre-generated):**
   ```bash
   python ml_models/train_models.py
   ```

3. **Start the FastAPI server:**
   ```bash
   python -m uvicorn app.main:app --reload --port 8000
   ```

4. **Open your browser:**
   - **Web App:** Visit [http://localhost:8000/](http://localhost:8000/)
   - **Interactive API Docs (OpenAPI / Swagger):** Visit [http://localhost:8000/docs](http://localhost:8000/docs)

---

### Option 2: Run with Docker Compose

To run PostgreSQL, Redis, and the Backend together in isolated containers:

```bash
docker-compose up --build
```

The application will be accessible at [http://localhost:8000/](http://localhost:8000/).

---

## 🧪 Running the Test Suite

The comprehensive Pytest suite validates all security, authentication, cross-user isolation, injection defense, and diary capabilities:

```bash
cd backend
python -m pytest tests/ -v
```

### Verified Test Cases:
- `test_registration_validation`: Strict password complexity (min 12 chars, variety) and mandatory disclaimer acceptance.
- `test_login_failure_and_lockout`: Generic 401 error and progressive 423 lockout on 5th failure with `Retry-After`.
- `test_refresh_token_rotation_and_logout`: Revocation of used refresh tokens and logout invalidation.
- `test_single_use_password_reset`: Time-limited single-use reset token verification.
- `test_cross_user_isolation`: User A cannot read, edit, or delete User B's diary entries; unowned records return 404 (not 403) to prevent ID enumeration.
- `test_sql_injection_payloads`: SQL injection strings in login and note searches are handled safely without leaks.
- `test_xss_sanitization`: `<script>` and `onerror` payloads in notes and tags are sanitized.
- `test_pydantic_strict_validation`: Extra fields rejected (`extra="forbid"`), clinical range limits enforced.
- `test_prediction_endpoint`: Model inference for diabetes and heart disease with SHAP factor attributions.
- `test_dangerous_range_alert`: Calm physician advisory trigger for extreme biomarkers.
- `test_diary_trends_and_compare`: Chronological trends calculation, status trajectory, side-by-side delta comparison, and CSV export.
- `test_account_deletion_cascades_data`: Cascade deletion of user, tokens, entries, and goals.

---

## 📡 API Endpoint Reference

### Authentication
- `POST /api/v1/auth/register` — Create account with password validation and disclaimer consent.
- `POST /api/v1/auth/login` — Sign in (rate-limited, progressive lockout, sets secure HttpOnly cookie).
- `POST /api/v1/auth/refresh` — Rotate refresh token and issue fresh access token.
- `POST /api/v1/auth/logout` — Revoke refresh token and clear cookies.
- `POST /api/v1/auth/forgot-password` — Issue single-use password reset token (no email enumeration).
- `POST /api/v1/auth/reset-password` — Consume reset token and update password.
- `GET /api/v1/auth/me` — Retrieve active user profile.

### Prediction & Models
- `POST /api/v1/predict` — Calculate risk probability, risk tier, SHAP factors, and clinical warnings (anonymous or authenticated; rate-limited to 30/min).
- `GET /api/v1/model/metrics` — Cross-validation metrics (Recall, ROC-AUC, Precision, ROC curve points).

### Health Diary
- `GET /api/v1/diary` — List user's entries (pagination, condition, risk, tag, and keyword search).
- `POST /api/v1/diary` — Save prediction and lifestyle log to diary (rate-limited to 60/hr).
- `GET /api/v1/diary/{id}` — Retrieve specific diary entry (404 for unowned IDs).
- `PUT /api/v1/diary/{id}` — Update note, mood, tags, or lifestyle metrics.
- `DELETE /api/v1/diary/{id}` — Remove entry.
- `GET /api/v1/diary/trends` — Time-series trend points and trajectory indicator.
- `GET /api/v1/diary/compare?id_a={id}&id_b={id}` — Compare two entries side by side.
- `GET /api/v1/diary/export?format=csv` — Download complete diary as CSV.

### Goals & Account
- `GET /api/v1/goals` — Retrieve active wellness habit goals.
- `POST /api/v1/goals` — Create a habit goal.
- `DELETE /api/v1/goals/{id}` — Remove a goal.
- `POST /api/v1/account/change-password` — Update password with current password verification.
- `GET /api/v1/account/export-data` — Complete JSON export for GDPR data portability.
- `DELETE /api/v1/account` — Permanently delete account and all cascading health data.
- `GET /health` — Liveness health check probe (no internal details disclosed).

---

## 🔒 Security Architecture Highlights

1. **Argon2id Password Storage:** Complies with OWASP guidelines using `time_cost=3`, `memory_cost=64MB`, and `parallelism=4`.
2. **Timing Attack Protection:** Uses constant-time password verification on unknown usernames with precomputed dummy hashes.
3. **Defense-in-Depth Rate Limiting:** Sliding-window rate limiter via Redis with thread-safe in-memory sliding window fallback.
4. **Security Headers:** Strict HTTP response headers including `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and a hardened Content Security Policy (CSP).
5. **No Measurement Logging:** Only request IDs, endpoints, HTTP status codes, and latency are logged; raw clinical biomarkers and auth tokens are never written to server logs.
6. **Integrity Checksums:** SHA-256 hashes of ML model artifacts are verified against `checksums.json` at startup.

---

## 📜 License & Disclaimers

Distributed for educational and research evaluation under the MIT License.
HealthRisk AI estimates are strictly for instructional demonstration and must never replace medical diagnosis, consultation, or treatment by a qualified healthcare professional.
