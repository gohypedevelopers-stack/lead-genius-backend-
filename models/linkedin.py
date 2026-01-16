"""
LinkedIn credential models.
Supports both user-level and organization-level LinkedIn connections.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class LinkedInCredential(SQLModel, table=True):
    """
    Stores LinkedIn OAuth credentials.
    Can be linked to either a User (personal) or Organization (shared).
    """
    __tablename__ = "linkedin_credential"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    
    # Either user_id OR org_id should be set, not both
    user_id: Optional[uuid.UUID] = Field(default=None, foreign_key="user.id", index=True)
    org_id: Optional[uuid.UUID] = Field(default=None, foreign_key="organization.id", index=True)
    
    # Credential type
    credential_type: str = Field(default="personal", index=True)  # personal, organization
    
    # OAuth tokens
    access_token: str
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    
    # LinkedIn profile info (cached)
    linkedin_profile_id: Optional[str] = None
    linkedin_profile_name: Optional[str] = None
    linkedin_profile_url: Optional[str] = None
    
    # Subscription info
    has_sales_navigator: bool = Field(default=False)
    
    # Status
    is_active: bool = Field(default=True)
    last_used_at: Optional[datetime] = None
    
    # For org credentials, who connected it
    connected_by_user_id: Optional[uuid.UUID] = Field(default=None, foreign_key="user.id")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class LinkedInPreference(SQLModel, table=True):
    """
    User's preference for which LinkedIn account to use in each organization.
    """
    __tablename__ = "linkedin_preference"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    org_id: uuid.UUID = Field(foreign_key="organization.id", index=True)
    
    # Which credential to use
    use_personal: bool = Field(default=True)  # True = personal, False = org's shared
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
