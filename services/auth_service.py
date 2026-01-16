"""
Authentication service - handles all auth operations.
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlmodel.ext.asyncio.session import AsyncSession

from backend.config import settings
from backend.core.security import (
    get_password_hash, 
    verify_password, 
    create_access_token, 
    create_refresh_token,
    verify_token,
    decode_token
)
from backend.core.exceptions import (
    raise_already_exists, 
    raise_unauthorized, 
    raise_not_found,
    raise_validation_error
)
from backend.repositories.user_repo import UserRepository, OrganizationRepository
from backend.repositories.token_repo import (
    RefreshTokenRepository, 
    PasswordResetTokenRepository,
    EmailVerificationTokenRepository
)
from backend.repositories.activity_repo import ActivityLogRepository
from backend.models.user import User, Organization
from backend.models.activity import Actions
from backend.services.email_service import get_email_service


class AuthService:
    """Service for authentication operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.org_repo = OrganizationRepository(session)
        self.refresh_token_repo = RefreshTokenRepository(session)
        self.password_reset_repo = PasswordResetTokenRepository(session)
        self.email_verification_repo = EmailVerificationTokenRepository(session)
        self.activity_repo = ActivityLogRepository(session)
        self.email_service = get_email_service()
    
    async def register(
        self, 
        email: str, 
        password: str, 
        org_name: str,
        full_name: Optional[str] = None
    ) -> dict:
        """Register a new user with organization."""
        # Check if email already exists
        existing = await self.user_repo.get_by_email(email)
        if existing:
            raise_already_exists("User", "email", email)
        
        # Hash password
        password_hash = get_password_hash(password)
        
        # Create user with org and membership
        user, org, membership = await self.user_repo.create_with_org(
            email=email,
            password_hash=password_hash,
            org_name=org_name,
            full_name=full_name
        )
        
        # Log activity
        await self.activity_repo.log(
            org_id=org.id,
            actor_id=user.id,
            action=Actions.USER_REGISTERED,
            entity_type="user",
            entity_id=user.id,
            description=f"User {email} registered"
        )
        
        # Create email verification token
        verification_token = await self.email_verification_repo.create_token(user.id, email)
        
        # Send verification email
        await self.email_service.send_verification_email(
            to=email,
            token=verification_token.token,
            base_url=settings.FRONTEND_URL
        )
        
        # Build response
        response = {
            "message": "User registered successfully. Please check your email to verify your account.",
            "user_id": str(user.id),
            "org_id": str(org.id)
        }
        
        # In DEV_MODE, include the token for easy testing
        if settings.DEV_MODE:
            response["_dev_verification_token"] = verification_token.token
            response["_dev_note"] = "This token is only returned in development mode"
        
        return response
    
    async def login(
        self, 
        email: str, 
        password: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> dict:
        """Authenticate user and return tokens."""
        # Get user
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise_unauthorized("Incorrect email or password")
        
        # Verify password
        if not verify_password(password, user.password_hash):
            raise_unauthorized("Incorrect email or password")
        
        # Check if active
        if not user.is_active:
            raise_unauthorized("User account is deactivated")
        
        # Create tokens
        token_data = {
            "sub": user.email,
            "user_id": str(user.id),
            "org_id": str(user.current_org_id) if user.current_org_id else None
        }
        
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        # Decode refresh token to get jti
        refresh_payload = decode_token(refresh_token)
        
        # Store refresh token
        await self.refresh_token_repo.create_token(
            user_id=user.id,
            jti=refresh_payload["jti"],
            token=refresh_token,
            user_agent=user_agent,
            ip_address=ip_address
        )
        
        # Update last login
        await self.user_repo.update_last_login(user.id)
        
        # Log activity
        await self.activity_repo.log(
            org_id=user.current_org_id,
            actor_id=user.id,
            action=Actions.USER_LOGGED_IN,
            entity_type="user",
            entity_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
    
    async def refresh_access_token(self, refresh_token: str) -> dict:
        """Get new access token using refresh token."""
        # Verify the refresh token
        payload = verify_token(refresh_token, "refresh")
        if not payload:
            raise_unauthorized("Invalid or expired refresh token")
        
        # Check if token is revoked
        jti = payload.get("jti")
        is_valid = await self.refresh_token_repo.is_valid(jti)
        if not is_valid:
            raise_unauthorized("Refresh token has been revoked")
        
        # Create new access token
        token_data = {
            "sub": payload.get("sub"),
            "user_id": payload.get("user_id"),
            "org_id": payload.get("org_id")
        }
        
        access_token = create_access_token(token_data)
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
    
    async def logout(self, refresh_token: str) -> bool:
        """Logout by revoking refresh token."""
        payload = decode_token(refresh_token)
        if payload:
            jti = payload.get("jti")
            token = await self.refresh_token_repo.get_by_jti(jti)
            if token:
                await self.refresh_token_repo.revoke(token.id)
                return True
        return False
    
    async def logout_all(self, user_id: uuid.UUID) -> int:
        """Logout from all devices by revoking all refresh tokens."""
        return await self.refresh_token_repo.revoke_all_for_user(user_id)
    
    async def forgot_password(self, email: str) -> dict:
        """Initiate password reset flow."""
        response = {
            "message": "If the email exists, a reset link has been sent"
        }
        
        user = await self.user_repo.get_by_email(email)
        if not user:
            # Don't reveal if email exists
            return response
        
        # Create reset token
        reset_token = await self.password_reset_repo.create_token(user.id)
        
        # Send password reset email
        await self.email_service.send_password_reset_email(
            to=email,
            token=reset_token.token,
            base_url=settings.FRONTEND_URL
        )
        
        # In DEV_MODE, include the token for easy testing
        if settings.DEV_MODE:
            response["_dev_reset_token"] = reset_token.token
        
        return response
    
    async def reset_password(self, token: str, new_password: str) -> bool:
        """Reset password using token."""
        # Validate token
        reset_token = await self.password_reset_repo.get_valid_token(token)
        if not reset_token:
            raise_validation_error("Invalid or expired reset token")
        
        # Update password
        password_hash = get_password_hash(new_password)
        await self.user_repo.update_password(reset_token.user_id, password_hash)
        
        # Mark token as used
        await self.password_reset_repo.mark_used(reset_token.id)
        
        # Revoke all refresh tokens for security
        await self.refresh_token_repo.revoke_all_for_user(reset_token.user_id)
        
        # Log activity
        user = await self.user_repo.get(reset_token.user_id)
        if user:
            await self.activity_repo.log(
                org_id=user.current_org_id,
                actor_id=user.id,
                action=Actions.PASSWORD_RESET,
                entity_type="user",
                entity_id=user.id,
                description="Password was reset"
            )
        
        return True
    
    async def verify_email(self, token: str) -> bool:
        """Verify email using token."""
        verification_token = await self.email_verification_repo.get_valid_token(token)
        if not verification_token:
            raise_validation_error("Invalid or expired verification token")
        
        # Mark user as verified
        await self.user_repo.verify_email(verification_token.user_id)
        
        # Mark token as verified
        await self.email_verification_repo.mark_verified(verification_token.id)
        
        # Log activity
        user = await self.user_repo.get(verification_token.user_id)
        if user:
            await self.activity_repo.log(
                org_id=user.current_org_id,
                actor_id=user.id,
                action=Actions.EMAIL_VERIFIED,
                entity_type="user",
                entity_id=user.id,
                description="Email verified"
            )
        
        return True
    
    async def resend_verification(self, email: str) -> dict:
        """Resend verification email."""
        response = {
            "message": "If the email exists and is not verified, a new verification link has been sent"
        }
        
        user = await self.user_repo.get_by_email(email)
        if not user:
            return response
        
        if user.is_verified:
            return response
        
        # Create new verification token
        verification_token = await self.email_verification_repo.create_token(user.id, email)
        
        # Send verification email
        await self.email_service.send_verification_email(
            to=email,
            token=verification_token.token,
            base_url=settings.FRONTEND_URL
        )
        
        # In DEV_MODE, include the token for easy testing
        if settings.DEV_MODE:
            response["_dev_verification_token"] = verification_token.token
        
        return response
    
    async def change_password(
        self, 
        user_id: uuid.UUID, 
        current_password: str, 
        new_password: str
    ) -> bool:
        """Change password for logged-in user."""
        user = await self.user_repo.get(user_id)
        if not user:
            raise_not_found("User")
        
        # Verify current password
        if not verify_password(current_password, user.password_hash):
            raise_unauthorized("Current password is incorrect")
        
        # Update password
        password_hash = get_password_hash(new_password)
        await self.user_repo.update_password(user_id, password_hash)
        
        return True
