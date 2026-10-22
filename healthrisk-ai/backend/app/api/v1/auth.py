from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import enforce_rate_limit
from app.schemas.schemas import (
    RegisterRequest, LoginRequest, ForgotPasswordRequest,
    ResetPasswordRequest, UserOut, TokenResponse
)
from app.services.auth_service import AuthService
from app.api.deps import get_current_user
from app.models.entities import User
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(
    request_data: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Register a new user account with strict password validation and disclaimer consent."""
    enforce_rate_limit(request, scope="register", max_requests=10, window_seconds=60)
    user = AuthService.register_user(db, request_data, request)
    return user

@router.post("/login", response_model=TokenResponse)
def login(
    request_data: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Authenticate user with rate limiting (5 attempts/min per account) and progressive lockout."""
    enforce_rate_limit(request, scope="login_ip", max_requests=100, window_seconds=60)
    user, access_token, refresh_token = AuthService.authenticate_user(db, request_data, request)

    # Set secure HttpOnly cookies
    cookie_max_age = 30 * 86400 if request_data.remember_me else 7 * 86400
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.ENVIRONMENT != "development",
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.ENVIRONMENT != "development",
        samesite="lax",
        max_age=cookie_max_age
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(user)
    )

@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Rotate refresh token and issue a fresh access token."""
    raw_token = request.cookies.get("refresh_token")
    if not raw_token:
        # Check header fallback for testing
        auth_header = request.headers.get("X-Refresh-Token")
        if auth_header:
            raw_token = auth_header
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token missing.")

    user, new_access, new_refresh = AuthService.rotate_refresh_token(db, raw_token, request)

    response.set_cookie(
        key="access_token",
        value=new_access,
        httponly=True,
        secure=settings.ENVIRONMENT != "development",
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=settings.ENVIRONMENT != "development",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    )

    return TokenResponse(
        access_token=new_access,
        token_type="bearer",
        user=UserOut.model_validate(user)
    )

@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Revoke refresh token and clear session cookies."""
    raw_token = request.cookies.get("refresh_token") or request.headers.get("X-Refresh-Token")
    if raw_token:
        AuthService.revoke_refresh_token(db, raw_token, request)

    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "Logged out successfully."}

@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(
    request_data: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Generate a single-use time-limited reset token without disclosing email registration status."""
    enforce_rate_limit(request, scope="forgot_pw", max_requests=5, window_seconds=300)
    reset_token = AuthService.create_password_reset_token(db, request_data.email, request)
    # Generic message returned to prevent email enumeration
    res = {
        "message": "If an account matches that email, a password reset link has been dispatched."
    }
    # In development / educational demo mode, return the token for ease of use
    if settings.ENVIRONMENT == "development" and reset_token:
        res["demo_reset_token"] = reset_token
    return res

@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(
    request_data: ResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Consume single-use token and update password."""
    AuthService.reset_password(db, request_data.token, request_data.new_password, request)
    return {"message": "Password has been successfully updated. You may now sign in."}

@router.post("/verify-email", status_code=status.HTTP_200_OK)
def verify_email():
    """Educational demo verification confirmation."""
    return {"message": "Email address verified successfully."}

@router.get("/me", response_model=UserOut)
def get_current_user_profile(user: User = Depends(get_current_user)):
    """Retrieve profile of authenticated user."""
    return user
