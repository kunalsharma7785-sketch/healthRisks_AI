import pytest

def test_prediction_endpoint(client):
    # Diabetes prediction
    res = client.post("/api/v1/predict", json={
        "condition": "diabetes",
        "measurements": {
            "age": 52,
            "sex": 0,
            "bmi": 34.2,
            "blood_pressure": 138.0,
            "glucose": 168.0,
            "cholesterol": 220.0,
            "pregnancies": 3,
            "insulin": 140.0
        }
    })
    assert res.status_code == 200
    data = res.json()
    assert 0.0 <= data["probability"] <= 1.0
    assert data["risk_level"] in ["Low", "Moderate", "High"]
    assert len(data["top_factors"]) <= 5
    assert "educational estimate" in data["disclaimer"].lower()

    # Heart disease prediction
    res_heart = client.post("/api/v1/predict", json={
        "condition": "heart_disease",
        "measurements": {
            "age": 60,
            "sex": 1,
            "bmi": 29.0,
            "blood_pressure": 150.0,
            "glucose": 130.0,
            "cholesterol": 260.0,
            "chest_pain_type": 2,
            "max_heart_rate": 125.0
        }
    })
    assert res_heart.status_code == 200
    heart_data = res_heart.json()
    assert heart_data["condition"] == "heart_disease"
    assert len(heart_data["top_factors"]) > 0

def test_dangerous_range_alert(client):
    res = client.post("/api/v1/predict", json={
        "condition": "diabetes",
        "measurements": {
            "age": 45,
            "sex": 1,
            "bmi": 26.0,
            "blood_pressure": 195.0,  # Hypertensive crisis range
            "glucose": 350.0,         # Severe hyperglycemia
            "cholesterol": 210.0
        }
    })
    assert res.status_code == 200
    data = res.json()
    assert data["dangerous_range_warning"] is not None
    assert "healthcare professional" in data["dangerous_range_warning"].lower()

def test_diary_trends_and_compare(client, auth_headers):
    # Create entry 1
    client.post("/api/v1/diary", headers=auth_headers, json={
        "condition": "diabetes",
        "measurements": {
            "age": 50,
            "sex": 0,
            "bmi": 32.0,
            "blood_pressure": 140.0,
            "glucose": 160.0,
            "cholesterol": 220.0,
            "pregnancies": 1,
            "insulin": 120.0
        },
        "probability": 0.70,
        "risk_level": "High",
        "model_version": "1.0.0",
        "top_factors": [],
        "note": "Initial baseline reading"
    })

    # Create entry 2 (improved)
    client.post("/api/v1/diary", headers=auth_headers, json={
        "condition": "diabetes",
        "measurements": {
            "age": 50,
            "sex": 0,
            "bmi": 30.0,
            "blood_pressure": 125.0,
            "glucose": 115.0,
            "cholesterol": 190.0,
            "pregnancies": 1,
            "insulin": 90.0
        },
        "probability": 0.35,
        "risk_level": "Moderate",
        "model_version": "1.0.0",
        "top_factors": [],
        "note": "After 4 weeks of brisk walking and dietary adjustments"
    })

    # Test trends
    trends_res = client.get("/api/v1/diary/trends?condition=diabetes", headers=auth_headers)
    assert trends_res.status_code == 200
    trends = trends_res.json()
    assert len(trends["points"]) == 2
    assert trends["status_indicator"] == "improving"

    # Test compare
    entries_res = client.get("/api/v1/diary", headers=auth_headers)
    entries = entries_res.json()
    assert len(entries) >= 2
    id1, id2 = entries[0]["id"], entries[1]["id"]
    compare_res = client.get(f"/api/v1/diary/compare?id_a={id1}&id_b={id2}", headers=auth_headers)
    assert compare_res.status_code == 200
    compare_data = compare_res.json()
    assert "metric_differences" in compare_data
    assert "plain_english_summary" in compare_data

    # Test CSV export
    export_res = client.get("/api/v1/diary/export?format=csv", headers=auth_headers)
    assert export_res.status_code == 200
    assert "text/csv" in export_res.headers["content-type"]
    assert "Estimated Risk (%)" in export_res.text

def test_account_deletion_cascades_data(client):
    # Register fresh user
    email = "delete_me@example.com"
    pw = "DeletePassword123!@"
    client.post("/api/v1/auth/register", json={
        "full_name": "Ephemeral User",
        "email": email,
        "password": pw,
        "confirm_password": pw,
        "terms_accepted": True
    })
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Add diary entry and goal
    client.post("/api/v1/diary", headers=headers, json={
        "condition": "diabetes",
        "measurements": {"age": 35, "sex": 1, "bmi": 24.0, "blood_pressure": 120.0, "glucose": 100.0, "cholesterol": 180.0},
        "probability": 0.2, "risk_level": "Low", "model_version": "1.0.0", "top_factors": []
    })
    client.post("/api/v1/goals", headers=headers, json={
        "title": "Keep glucose under 100",
        "target_metric": "glucose",
        "target_value": 100.0,
        "unit": "mg/dL",
        "direction": "under"
    })

    # Delete account
    del_res = client.delete("/api/v1/account", headers=headers)
    assert del_res.status_code == 200

    # User cannot login anymore
    relogin = client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    assert relogin.status_code == 401
