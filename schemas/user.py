"""
User and Organization schemas.
"""
import uuid
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr


# User schemas
class UserResponse(BaseModel):
    """User details response (with current org context)."""
    id: uuid.UUID
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_verified: bool
    current_org_id: Optional[uuid.UUID] = None
    role: Optional[str] = None  # Role in current org, fetched from OrganizationMember
    created_at: datetime
    last_login_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Update user profile."""
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


# Organization schemas
class OrganizationResponse(BaseModel):
    """Organization details response."""
    id: uuid.UUID
    name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    business_model: Optional[str] = None
    stage: Optional[str] = None
    logo_url: Optional[str] = None
    timezone: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class OrganizationUpdate(BaseModel):
    """Update organization profile."""
    name: Optional[str] = None
    domain: Optional[str] = None
    industry: Optional[str] = None
    business_model: Optional[str] = None
    stage: Optional[str] = None
    logo_url: Optional[str] = None
    timezone: Optional[str] = None
