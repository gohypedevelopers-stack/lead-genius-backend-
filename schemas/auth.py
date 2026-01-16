"""
Authentication schemas.
"""
from typing import Optional
from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str
    org_name: str
    full_name: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@company.com",
                "password": "securepassword123",
                "org_name": "Acme Corp",
                "full_name": "John Doe"
            }
        }


class LoginRequest(BaseModel):
    """User login request."""
    email: EmailStr
    password: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@company.com",
                "password": "securepassword123"
            }
        }


class TokenResponse(BaseModel):
    """Token response after login."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    """Refresh token request."""
    refresh_token: str


class AccessTokenResponse(BaseModel):
    """New access token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class PasswordResetRequest(BaseModel):
    """Request password reset."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Confirm password reset with token."""
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    """Change password for logged-in user."""
    current_password: str
    new_password: str


class EmailVerificationRequest(BaseModel):
    """Verify email with token."""
    token: str


class ResendVerificationRequest(BaseModel):
    """Resend verification email."""
    email: EmailStr
