import uuid
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status, Request

from app.models.entities import User, RefreshToken, PasswordResetToken
from app.schemas.schemas import RegisterRequest, LoginRequest, UserOut
from app.core.security import (
    hash_password, verify_password, hash_token,
    create_access_token, create_refresh_token, decode_token,
    validate_password_strength
)
from app.core.rate_limit import RateLimiter, get_client_ip
from app.core.audit import AuditLogger
from app.core.config import settings

def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

GENERIC_AUTH_ERROR = "Email or password is incorrect."

class AuthService:

    @staticmethod
    def register_user(db: Session, request: RegisterRequest, req: Request) -> User:
        ip = get_client_ip(req)
        
        # Validate password rules
        strength = validate_password_strength(request.password)
        if not strength["is_valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=strength["errors"][0]
            )
            
        # Check if email is already taken
        existing = db.query(User).filter(User.email == request.email.lower().strip()).first()
        if existing:
            # We return 400 for duplicate during register
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email address already exists."
            )
            
        hashed = hash_password(request.password)
        user = User(
            email=request.email.lower().strip(),
            full_name=request.full_name.strip(),
            hashed_password=hashed,
            is_verified=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        AuditLogger.log_event("USER_REGISTER", "SUCCESS", ip, str(user.id), {"email": user.email})
        return user

    @staticmethod
    def authenticate_user(db: Session, request: LoginRequest, req: Request) -> Tuple[User, str, str]:
        ip = get_client_ip(req)
        email = request.email.lower().strip()
        account_key = f"{email}:{ip}"
        
        # 1. Check progressive lockout
        is_locked, remaining_sec = RateLimiter.check_lockout(account_key)
        if is_locked:
            minutes = (remaining_sec // 60) + 1
            AuditLogger.log_event("LOGIN_ATTEMPT_LOCKED", "BLOCKED", ip, details={"email": email, "remaining_sec": remaining_sec})
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Account temporarily locked due to repeated failed attempts. Please wait {remaining_sec} seconds before trying again.",
                headers={"Retry-After": str(remaining_sec)}
            )
            
        # 2. Query user
        user = db.query(User).filter(User.email == email).first()
        
        # Constant-time dummy verify to prevent timing oracle if user does not exist
        dummy_hash = "$argon2id$v=19$m=65536,t=3,p=4$RMwCEnhHmOgwRZqagnFz/Q$BrWWFZrqlyqB8RGamqpCipPw1zu/r7LnIcVwKvIZzjU"
        
        is_valid = False
        if user:
            is_valid = verify_password(request.password, user.hashed_password)
        else:
            verify_password(request.password, dummy_hash)
            
        if not is_valid:
            failures, lockout_sec, locked = RateLimiter.record_login_failure(account_key)
            AuditLogger.log_event("LOGIN_FAILED", "FAILURE", ip, str(user.id) if user else None, {"failures": failures})
            
            if locked:
                AuditLogger.log_event("LOCKOUT_TRIGGERED", "LOCKED", ip, str(user.id) if user else None, {"duration": lockout_sec})
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail=f"Too many failed login attempts. Your account has been temporarily locked for {lockout_sec // 60} minutes.",
                    headers={"Retry-After": str(lockout_sec)}
                )
                
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=GENERIC_AUTH_ERROR
            )
            
        # Success: reset failures and issue tokens
        RateLimiter.reset_login_failures(account_key)
        
        access_token = create_access_token({"sub": str(user.id), "email": user.email})
        
        # Refresh token expiration (longer if remember_me)
        refresh_days = 30 if request.remember_me else settings.REFRESH_TOKEN_EXPIRE_DAYS
        refresh_delta = timedelta(days=refresh_days)
        raw_refresh_token = create_refresh_token({"sub": str(user.id), "jti": str(uuid.uuid4())}, expires_delta=refresh_delta)
        
        # Store hashed refresh token in database
        rf_entry = RefreshToken(
            user_id=user.id,
            token_hash=hash_token(raw_refresh_token),
            expires_at=utc_now() + refresh_delta
        )
        db.add(rf_entry)
        db.commit()
        
        AuditLogger.log_event("LOGIN_SUCCESS", "SUCCESS", ip, str(user.id))
        return user, access_token, raw_refresh_token

    @staticmethod
    def rotate_refresh_token(db: Session, raw_token: str, req: Request) -> Tuple[User, str, str]:
        ip = get_client_ip(req)
        payload = decode_token(raw_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")
            
        user_id = int(payload.get("sub", 0))
        token_hashed = hash_token(raw_token)
        
        db_token = db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hashed,
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None)
        ).first()
        
        if not db_token or db_token.expires_at < utc_now():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Expired or revoked refresh token.")
            
        # Revoke used refresh token
        db_token.revoked_at = utc_now()
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
            
        # Generate new pair (rotation)
        new_access = create_access_token({"sub": str(user.id), "email": user.email})
        new_refresh = create_refresh_token({"sub": str(user.id), "jti": str(uuid.uuid4())})
        
        new_rf_entry = RefreshToken(
            user_id=user.id,
            token_hash=hash_token(new_refresh),
            expires_at=utc_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
        db.add(new_rf_entry)
        db.commit()
        
        AuditLogger.log_event("TOKEN_ROTATED", "SUCCESS", ip, str(user.id))
        return user, new_access, new_refresh

    @staticmethod
    def revoke_refresh_token(db: Session, raw_token: str, req: Request):
        ip = get_client_ip(req)
        token_hashed = hash_token(raw_token)
        db_token = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hashed).first()
        if db_token:
            db_token.revoked_at = utc_now()
            db.commit()
            AuditLogger.log_event("LOGOUT", "SUCCESS", ip, str(db_token.user_id))

    @staticmethod
    def create_password_reset_token(db: Session, email: str, req: Request) -> Optional[str]:
        ip = get_client_ip(req)
        user = db.query(User).filter(User.email == email.lower().strip()).first()
        # Always return cleanly to avoid email enumeration
        if not user:
            AuditLogger.log_event("PASSWORD_RESET_REQUEST_UNKNOWN", "INFO", ip, details={"email": email})
            return None
            
        raw_reset_token = f"reset_{uuid.uuid4().hex}_{int(time.time())}"
        hashed = hash_token(raw_reset_token)
        expires = utc_now() + timedelta(minutes=30)
        
        token_entry = PasswordResetToken(
            user_id=user.id,
            token_hash=hashed,
            expires_at=expires
        )
        db.add(token_entry)
        db.commit()
        
        AuditLogger.log_event("PASSWORD_RESET_TOKEN_ISSUED", "SUCCESS", ip, str(user.id))
        return raw_reset_token

    @staticmethod
    def reset_password(db: Session, raw_token: str, new_password: str, req: Request):
        ip = get_client_ip(req)
        strength = validate_password_strength(new_password)
        if not strength["is_valid"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=strength["errors"][0])
            
        hashed = hash_token(raw_token)
        token_entry = db.query(PasswordResetToken).filter(
            PasswordResetToken.token_hash == hashed,
            PasswordResetToken.used_at.is_(None)
        ).first()
        
        if not token_entry or token_entry.expires_at < utc_now():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token.")
            
        user = db.query(User).filter(User.id == token_entry.user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
            
        user.hashed_password = hash_password(new_password)
        token_entry.used_at = utc_now()
        
        # Revoke all existing refresh tokens for security
        db.query(RefreshToken).filter(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None)
        ).update({"revoked_at": utc_now()})
        
        db.commit()
        AuditLogger.log_event("PASSWORD_RESET_COMPLETED", "SUCCESS", ip, str(user.id))

    @staticmethod
    def change_password(db: Session, user_id: int, current_pw: str, new_pw: str, req: Request):
        ip = get_client_ip(req)
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not verify_password(current_pw, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")
            
        strength = validate_password_strength(new_pw)
        if not strength["is_valid"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=strength["errors"][0])
            
        user.hashed_password = hash_password(new_pw)
        db.commit()
        AuditLogger.log_event("PASSWORD_CHANGED", "SUCCESS", ip, str(user.id))
