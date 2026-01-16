import uuid
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship

from datetime import datetime

class Organization(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    business_model: Optional[str] = None
    stage: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    users: List["User"] = Relationship(back_populates="organization")

class User(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    org_id: Optional[uuid.UUID] = Field(default=None, foreign_key="organization.id")
    email: str = Field(unique=True, index=True)
    full_name: Optional[str] = None
    password_hash: str
    
    organization: Optional[Organization] = Relationship(back_populates="users")
