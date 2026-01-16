from datetime import datetime
import uuid
from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field
from sqlalchemy.dialects.postgresql import JSONB

class ActivityLog(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    org_id: uuid.UUID = Field(foreign_key="organization.id")
    actor_id: Optional[uuid.UUID] = Field(default=None, foreign_key="user.id")
    action: str
    entity_type: str  # lead, campaign, system
    entity_id: Optional[uuid.UUID] = None
    meta_data: Dict[str, Any] = Field(default={}, sa_type=JSONB)
    created_at: datetime = Field(default_factory=datetime.utcnow)
