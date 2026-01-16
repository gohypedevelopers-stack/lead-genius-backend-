"""
Organization schemas for API requests/responses.
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


# =============================================================================
# REQUEST SCHEMAS
# =============================================================================

class CreateOrganizationRequest(BaseModel):
    """Request to create a new organization."""
    name: str = Field(..., min_length=1, max_length=100)
    domain: Optional[str] = Field(None, max_length=100)
    industry: Optional[str] = None
    business_model: Optional[str] = None


class InviteUserRequest(BaseModel):
    """Request to invite a user to organization."""
    email: str
    role: str = Field(default="member", pattern="^(admin|member|viewer)$")


class UpdateMemberRoleRequest(BaseModel):
    """Request to update member's role."""
    role: str = Field(..., pattern="^(admin|member|viewer)$")


class UpdateOrganizationRequest(BaseModel):
    """Request to update organization details."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    domain: Optional[str] = None
    industry: Optional[str] = None
    business_model: Optional[str] = None
    stage: Optional[str] = None
    logo_url: Optional[str] = None
    timezone: Optional[str] = None


# =============================================================================
# RESPONSE SCHEMAS
# =============================================================================

class OrganizationResponse(BaseModel):
    """Organization details response."""
    id: str
    name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    business_model: Optional[str] = None
    stage: Optional[str] = None
    logo_url: Optional[str] = None
    timezone: str
    created_at: datetime


class OrganizationWithRoleResponse(BaseModel):
    """Organization with user's role in it."""
    id: str
    name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    role: str
    joined_at: str
    is_active: bool


class MemberResponse(BaseModel):
    """Member of an organization."""
    id: str
    user_id: str
    email: str
    full_name: Optional[str] = None
    role: str
    joined_at: str
    is_active: bool


class OrganizationListResponse(BaseModel):
    """List of user's organizations."""
    organizations: List[OrganizationWithRoleResponse]
    count: int


class MemberListResponse(BaseModel):
    """List of organization members."""
    members: List[MemberResponse]
    count: int


class SwitchOrgResponse(BaseModel):
    """Response after switching organization."""
    message: str
    organization: dict
    access_token: str
    token_type: str = "bearer"
