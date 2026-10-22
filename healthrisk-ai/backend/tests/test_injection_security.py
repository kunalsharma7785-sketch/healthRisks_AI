import pytest

def test_sql_injection_payloads(client, auth_headers):
    sqli_payloads = [
        "' OR 1=1 --",
        "'; DROP TABLE users; --",
        "UNION SELECT null, username, password FROM users --",
        "admin' --"
    ]
    for payload in sqli_payloads:
        # Test in login
        res = client.post("/api/v1/auth/login", json={
            "email": "researcher@example.com",
            "password": payload
        })
        # Must fail safely with 401, 423, or 429, not 500
        assert res.status_code in [401, 423, 429]

        # Test in search query
        search_res = client.get(f"/api/v1/diary?search={payload}", headers=auth_headers)
        assert search_res.status_code == 200

def test_xss_sanitization(client, auth_headers):
    xss_note = "<script>alert('XSS-ATTACK');</script><img src=x onerror=alert(1)>Test Note"
    xss_tags = ["<script>alert(2)</script>", "safe-tag", "malicious;DROP"]

    res = client.post("/api/v1/diary", headers=auth_headers, json={
        "condition": "diabetes",
        "measurements": {
            "age": 30,
            "sex": 1,
            "bmi": 24.0,
            "blood_pressure": 115.0,
            "glucose": 95.0,
            "cholesterol": 170.0,
            "pregnancies": 0,
            "insulin": 45.0
        },
        "probability": 0.12,
        "risk_level": "Low",
        "model_version": "1.0.0",
        "top_factors": [],
        "note": xss_note,
        "tags": xss_tags
    })
    assert res.status_code == 201
    data = res.json()
    # Script tag stripped or escaped
    assert "<script>" not in data["note"]
    assert "alert('XSS-ATTACK')" not in data["note"]
    # Tags stripped of unsafe characters
    for tag in data["tags"]:
        assert "<script>" not in tag

def test_pydantic_strict_validation(client):
    # Extra field rejected
    res = client.post("/api/v1/predict", json={
        "condition": "diabetes",
        "measurements": {
            "age": 40,
            "sex": 1,
            "bmi": 25.0,
            "blood_pressure": 120.0,
            "glucose": 100.0,
            "cholesterol": 180.0,
            "malicious_extra_field": "injected"
        }
    })
    assert res.status_code == 422

    # Out of range values rejected
    res_range = client.post("/api/v1/predict", json={
        "condition": "diabetes",
        "measurements": {
            "age": 150,  # Max 120
            "sex": 1,
            "bmi": 25.0,
            "blood_pressure": 120.0,
            "glucose": 100.0,
            "cholesterol": 180.0
        }
    })
    assert res_range.status_code == 422
