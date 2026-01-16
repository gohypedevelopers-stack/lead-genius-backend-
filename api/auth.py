"""
Authentication API routes.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.database import get_session
from backend.services.auth_service import AuthService
from backend.schemas.auth import (
    RegisterRequest, TokenResponse, RefreshRequest, AccessTokenResponse,
    PasswordResetRequest, PasswordResetConfirm, ChangePasswordRequest,
    EmailVerificationRequest, ResendVerificationRequest
)
from backend.schemas.common import MessageResponse
from backend.api.deps import get_current_user, get_client_info
from backend.models.user import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register")
async def register(
    request: RegisterRequest,
    session: AsyncSession = Depends(get_session)
):
    """Register a new user with organization."""
    auth_service = AuthService(session)
    # Returns dict with message and user/org IDs
    # In DEV_MODE, also includes _dev_verification_token for testing
    return await auth_service.register(
        email=request.email,
        password=request.password,
        org_name=request.org_name,
        full_name=request.full_name
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
    session: AsyncSession = Depends(get_session)
):
    """Login and get access + refresh tokens."""
    auth_service = AuthService(session)
    client_info = get_client_info(request) if request else {}
    
    return await auth_service.login(
        email=form_data.username,
        password=form_data.password,
        user_agent=client_info.get("user_agent"),
        ip_address=client_info.get("ip_address")
    )


# Keep /token endpoint for backward compatibility
@router.post("/token", response_model=TokenResponse)
async def token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
    session: AsyncSession = Depends(get_session)
):
    """Login (alias for /login)."""
    return await login(form_data, request, session)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh_token(
    request: RefreshRequest,
    session: AsyncSession = Depends(get_session)
):
    """Get new access token using refresh token."""
    auth_service = AuthService(session)
    return await auth_service.refresh_access_token(request.refresh_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: RefreshRequest,
    session: AsyncSession = Depends(get_session)
):
    """Logout by revoking refresh token."""
    auth_service = AuthService(session)
    await auth_service.logout(request.refresh_token)
    return MessageResponse(message="Logged out successfully")


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Logout from all devices."""
    auth_service = AuthService(session)
    count = await auth_service.logout_all(current_user.id)
    return MessageResponse(message=f"Logged out from {count} devices")


@router.post("/forgot-password")
async def forgot_password(
    request: PasswordResetRequest,
    session: AsyncSession = Depends(get_session)
):
    """Request password reset."""
    auth_service = AuthService(session)
    # Returns dict with message
    # In DEV_MODE, also includes _dev_reset_token for testing
    return await auth_service.forgot_password(request.email)


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    request: PasswordResetConfirm,
    session: AsyncSession = Depends(get_session)
):
    """Reset password using token."""
    auth_service = AuthService(session)
    await auth_service.reset_password(request.token, request.new_password)
    return MessageResponse(message="Password reset successfully")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Change password for logged-in user."""
    auth_service = AuthService(session)
    await auth_service.change_password(
        current_user.id,
        request.current_password,
        request.new_password
    )
    return MessageResponse(message="Password changed successfully")


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    request: EmailVerificationRequest,
    session: AsyncSession = Depends(get_session)
):
    """Verify email using token."""
    auth_service = AuthService(session)
    await auth_service.verify_email(request.token)
    return MessageResponse(message="Email verified successfully")


@router.post("/resend-verification")
async def resend_verification(
    request: ResendVerificationRequest,
    session: AsyncSession = Depends(get_session)
):
    """Resend verification email."""
    auth_service = AuthService(session)
    # Returns dict with message
    # In DEV_MODE, also includes _dev_verification_token for testing
    return await auth_service.resend_verification(request.email)
