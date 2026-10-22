import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.services.ml_service import MLService

# Use isolated test database
TEST_DB_FILE = "./test_healthrisk.db"
if os.path.exists(TEST_DB_FILE):
    os.remove(TEST_DB_FILE)

test_engine = create_engine(
    f"sqlite:///{TEST_DB_FILE}",
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    Base.metadata.create_all(bind=test_engine)
    MLService.initialize()
    yield
    Base.metadata.drop_all(bind=test_engine)
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except Exception:
            pass

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture
def registered_user(client):
    email = "researcher@example.com"
    password = "SecurePassword123!@#"
    resp = client.post("/api/v1/auth/register", json={
        "full_name": "Dr. Jane Doe",
        "email": email,
        "password": password,
        "confirm_password": password,
        "terms_accepted": True
    })
    return {"email": email, "password": password, "user": resp.json()}

@pytest.fixture
def auth_headers(client, registered_user):
    login_resp = client.post("/api/v1/auth/login", json={
        "email": registered_user["email"],
        "password": registered_user["password"]
    })
    token = login_resp.json()["access_token"]
    refresh_token = login_resp.cookies.get("refresh_token")
    return {
        "Authorization": f"Bearer {token}",
        "refresh_token": refresh_token
    }
