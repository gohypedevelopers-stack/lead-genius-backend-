"""
User and Organization models.
Core entities for multi-tenant support with many-to-many relationship.
"""
import uuid
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship


class Organization(SQLModel, table=True):
    """
    Organization/Tenant model.
    All resources are scoped to an organization.
    """
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(index=True)
    domain: Optional[str] = Field(default=None, index=True)
    
    # Business profile
    industry: Optional[str] = None
    business_model: Optional[str] = None  # B2B, B2C, etc.
    stage: Optional[str] = None  # Startup, Growth, Enterprise
    
    # Settings
    logo_url: Optional[str] = None
    timezone: str = Field(default="UTC")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    members: List["OrganizationMember"] = Relationship(back_populates="organization")


class OrganizationMember(SQLModel, table=True):
    """
    Junction table for User-Organization many-to-many relationship.
    Allows users to belong to multiple organizations with different roles.
    """
    __tablename__ = "organization_member"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    org_id: uuid.UUID = Field(foreign_key="organization.id", index=True)
    
    # Role in this organization
    role: str = Field(default="member")  # owner, admin, member, viewer
    
    # Status
    is_active: bool = Field(default=True)
    
    # Timestamps
    joined_at: datetime = Field(default_factory=datetime.utcnow)
    invited_by: Optional[uuid.UUID] = None  # User who invited them
    
    # Relationships
    user: "User" = Relationship(back_populates="memberships")
    organization: Organization = Relationship(back_populates="members")


class User(SQLModel, table=True):
    """
    User model with authentication and profile info.
    Users can belong to multiple organizations via OrganizationMember.
    """
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    
    # Current active organization (for API scoping)
    current_org_id: Optional[uuid.UUID] = Field(default=None, foreign_key="organization.id", index=True)
    
    # Auth
    email: str = Field(unique=True, index=True)
    password_hash: str
    
    # Profile
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    
    # Verification status
    is_verified: bool = Field(default=False)
    is_active: bool = Field(default=True)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = None
    
    # Relationships
    memberships: List[OrganizationMember] = Relationship(back_populates="user")

