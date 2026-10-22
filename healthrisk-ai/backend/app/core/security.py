import html
import re
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from app.core.config import settings

# Argon2id password hasher with secure parameters
ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MB
    parallelism=4,
    hash_len=32,
    salt_len=16
)

COMMON_PASSWORDS = {
    "password1234", "123456789012", "qwertyuiop12", "adminadmin12",
    "password12345", "welcome12345", "iloveyou12345", "monkey123456"
}

def hash_password(password: str) -> str:
    """Hash password using Argon2id."""
    return ph.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password with constant-time resistance against timing attacks."""
    try:
        return ph.verify(hashed_password, plain_password)
    except Exception:
        return False

def validate_password_strength(password: str) -> Dict[str, Any]:
    """
    Validate password requirements:
    - At least 12 characters
    - Not in common passwords
    - Contains uppercase, lowercase, number, and special character
    """
    errors = []
    if len(password) < 12:
        errors.append("Password must be at least 12 characters long.")
    if password.lower() in COMMON_PASSWORDS:
        errors.append("This password is too common and easily guessed.")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", password):
        errors.append("Password must contain at least one number.")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        errors.append("Password must contain at least one special character.")

    # Calculate score 0-100
    score = 0
    if len(password) >= 12: score += 30
    if len(password) >= 16: score += 20
    if re.search(r"[A-Z]", password): score += 15
    if re.search(r"[a-z]", password): score += 10
    if re.search(r"\d", password): score += 15
    if re.search(r"[!@#$%^&*(),.?\":{}|<>]", password): score += 10

    return {
        "is_valid": len(errors) == 0,
        "score": min(score, 100),
        "errors": errors
    }

def hash_token(raw_token: str) -> str:
    """Hash sensitive refresh and reset tokens with SHA-256 for secure storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create short-lived JWT access token (15 mins default)."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create long-lived JWT refresh token (7 days default)."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "iat": now, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> Optional[dict]:
    """Decode and verify JWT signature and expiration."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None

def sanitize_text(text: Optional[str], max_length: int = 2000) -> Optional[str]:
    """Sanitize user input to prevent XSS and strip unsafe script elements."""
    if text is None:
        return None
    # Strip dangerous HTML tags
    cleaned = re.sub(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", "", text, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<\s*iframe[^>]*>.*?<\s*/\s*iframe\s*>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = html.escape(cleaned.strip())
    return cleaned[:max_length]

def sanitize_tags(tags: Optional[list]) -> list:
    """Sanitize tag list to prevent XSS."""
    if not tags:
        return []
    clean_tags = []
    for tag in tags:
        if isinstance(tag, str):
            clean_tag = re.sub(r"[^\w\s-]", "", tag).strip()
            if clean_tag and len(clean_tag) <= 50:
                clean_tags.append(clean_tag[:50])
    return clean_tags[:15]
