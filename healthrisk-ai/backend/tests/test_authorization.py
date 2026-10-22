import pytest

def test_cross_user_isolation(client):
    # Register User A
    client.post("/api/v1/auth/register", json={
        "full_name": "Alice User",
        "email": "alice@example.com",
        "password": "AlicePassword123!@",
        "confirm_password": "AlicePassword123!@",
        "terms_accepted": True
    })
    alice_login = client.post("/api/v1/auth/login", json={"email": "alice@example.com", "password": "AlicePassword123!@"})
    alice_token = alice_login.json()["access_token"]
    alice_headers = {"Authorization": f"Bearer {alice_token}"}

    # Register User B
    client.post("/api/v1/auth/register", json={
        "full_name": "Bob User",
        "email": "bob@example.com",
        "password": "BobPassword123!@#",
        "confirm_password": "BobPassword123!@#",
        "terms_accepted": True
    })
    bob_login = client.post("/api/v1/auth/login", json={"email": "bob@example.com", "password": "BobPassword123!@#"})
    bob_token = bob_login.json()["access_token"]
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    # Alice creates a diary entry
    create_res = client.post("/api/v1/diary", headers=alice_headers, json={
        "condition": "diabetes",
        "measurements": {
            "age": 45,
            "sex": 0,
            "bmi": 28.5,
            "blood_pressure": 125.0,
            "glucose": 140.0,
            "cholesterol": 195.0,
            "pregnancies": 2,
            "insulin": 85.0
        },
        "probability": 0.45,
        "risk_level": "Moderate",
        "model_version": "1.0.0",
        "top_factors": [
            {
                "feature": "Glucose",
                "raw_feature": "glucose",
                "value": 140.0,
                "impact": 40.0,
                "direction": "raises_risk",
                "explanation": "Glucose pushed risk up"
            }
        ],
        "note": "Alice's secret medical note"
    })
    assert create_res.status_code == 201
    entry_id = create_res.json()["id"]

    # Bob tries to GET Alice's entry -> returns 404 (not 403)
    bob_get = client.get(f"/api/v1/diary/{entry_id}", headers=bob_headers)
    assert bob_get.status_code == 404
    assert bob_get.json()["detail"] == "Diary entry not found."

    # Bob tries to PUT Alice's entry -> returns 404
    bob_put = client.put(f"/api/v1/diary/{entry_id}", headers=bob_headers, json={"note": "Hacked note"})
    assert bob_put.status_code == 404

    # Bob tries to DELETE Alice's entry -> returns 404
    bob_del = client.delete(f"/api/v1/diary/{entry_id}", headers=bob_headers)
    assert bob_del.status_code == 404

    # Alice can still access her entry
    alice_get = client.get(f"/api/v1/diary/{entry_id}", headers=alice_headers)
    assert alice_get.status_code == 200
    assert alice_get.json()["note"] == "Alice&#x27;s secret medical note"
