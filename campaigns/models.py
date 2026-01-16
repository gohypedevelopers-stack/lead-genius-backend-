from datetime import datetime
import uuid
from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy.dialects.postgresql import JSONB

class Campaign(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    org_id: uuid.UUID = Field(foreign_key="organization.id")
    name: str
    type: str  # social, group, search, csv
    status: str = Field(default="draft")  # draft, processing, completed, active
    settings: Dict[str, Any] = Field(default={}, sa_type=JSONB)
    leads_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
