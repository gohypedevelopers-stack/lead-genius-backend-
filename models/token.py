"""
Token models for authentication and verification.
Separate tables for proper token management and revocation.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class RefreshToken(SQLModel, table=True):
    """
    Refresh token for obtaining new access tokens.
    Stored in DB for revocation support.
    """
    __tablename__ = "refresh_token"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    
    token: str = Field(unique=True, index=True)  # The actual token string
    jti: str = Field(unique=True, index=True)  # JWT ID for matching with JWT payload
    
    # Status
    revoked: bool = Field(default=False)
    revoked_at: Optional[datetime] = None
    
    # Metadata
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime


class PasswordResetToken(SQLModel, table=True):
    """
    Token for password reset flow.
    Single-use, expires after configured time.
    """
    __tablename__ = "password_reset_token"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    
    token: str = Field(unique=True, index=True)
    
    # Status
    used: bool = Field(default=False)
    used_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime


class EmailVerificationToken(SQLModel, table=True):
    """
    Token for email verification.
    Sent after registration.
    """
    __tablename__ = "email_verification_token"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    
    token: str = Field(unique=True, index=True)
    email: str  # The email being verified (in case user changes email)
    
    # Status
    verified: bool = Field(default=False)
    verified_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
