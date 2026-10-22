import pytest

def test_registration_validation(client):
    # Under 12 characters
    res = client.post("/api/v1/auth/register", json={
        "full_name": "Test User",
        "email": "short@example.com",
        "password": "Short1!",
        "confirm_password": "Short1!",
        "terms_accepted": True
    })
    assert res.status_code in [400, 422]

    # Password mismatch
    res = client.post("/api/v1/auth/register", json={
        "full_name": "Test User",
        "email": "mismatch@test.com",
        "password": "ValidPassword123!",
        "confirm_password": "DifferentPassword123!",
        "terms_accepted": True
    })
    assert res.status_code == 422 or res.status_code == 400

    # Terms not accepted
    res = client.post("/api/v1/auth/register", json={
        "full_name": "Test User",
        "email": "noterms@test.com",
        "password": "ValidPassword123!",
        "confirm_password": "ValidPassword123!",
        "terms_accepted": False
    })
    assert res.status_code == 422 or res.status_code == 400

def test_login_failure_and_lockout(client):
    email = "lockout_victim@example.com"
    password = "CorrectPassword123!@"
    # Register
    client.post("/api/v1/auth/register", json={
        "full_name": "Victim User",
        "email": email,
        "password": password,
        "confirm_password": password,
        "terms_accepted": True
    })

    # 4 Failed login attempts -> generic error 401
    for _ in range(4):
        res = client.post("/api/v1/auth/login", json={
            "email": email,
            "password": "WrongPassword123!"
        })
        assert res.status_code == 401
        assert res.json()["detail"] == "Email or password is incorrect."

    # 5th attempt -> triggers progressive lockout (HTTP 423)
    res5 = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "WrongPassword123!"
    })
    assert res5.status_code == 423
    assert "locked" in res5.json()["detail"].lower()
    assert "Retry-After" in res5.headers

def test_refresh_token_rotation_and_logout(client):
    email = "rotation_user@example.com"
    pw = "RotationPassword123!@"
    client.post("/api/v1/auth/register", json={
        "full_name": "Rotation User",
        "email": email,
        "password": pw,
        "confirm_password": pw,
        "terms_accepted": True
    })

    # Login
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    assert login_res.status_code == 200
    cookies = login_res.cookies

    # Rotate refresh token
    refresh_res = client.post("/api/v1/auth/refresh", cookies=cookies)
    assert refresh_res.status_code == 200
    new_cookies = refresh_res.cookies
    assert "access_token" in new_cookies
    assert "refresh_token" in new_cookies

    # Old refresh token should now be rejected
    old_rejected = client.post("/api/v1/auth/refresh", cookies=cookies)
    assert old_rejected.status_code == 401

    # Logout
    logout_res = client.post("/api/v1/auth/logout", cookies=new_cookies)
    assert logout_res.status_code == 200

    # After logout, token cannot be refreshed
    logged_out_refresh = client.post("/api/v1/auth/refresh", cookies=new_cookies)
    assert logged_out_refresh.status_code == 401

def test_single_use_password_reset(client):
    email = "reset_user@example.com"
    pw = "OriginalPassword123!@"
    client.post("/api/v1/auth/register", json={
        "full_name": "Reset User",
        "email": email,
        "password": pw,
        "confirm_password": pw,
        "terms_accepted": True
    })

    # Forgot password
    forgot_res = client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert forgot_res.status_code == 200
    token = forgot_res.json().get("demo_reset_token")
    assert token is not None

    # Reset password
    new_pw = "BrandNewPassword123!#"
    reset_res = client.post("/api/v1/auth/reset-password", json={
        "token": token,
        "new_password": new_pw,
        "confirm_password": new_pw
    })
    assert reset_res.status_code == 200

    # Token cannot be reused (single-use)
    reuse_res = client.post("/api/v1/auth/reset-password", json={
        "token": token,
        "new_password": new_pw,
        "confirm_password": new_pw
    })
    assert reuse_res.status_code == 400

    # Can login with new password
    new_login = client.post("/api/v1/auth/login", json={"email": email, "password": new_pw})
    assert new_login.status_code == 200
