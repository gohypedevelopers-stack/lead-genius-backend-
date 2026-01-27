import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field
from sqlalchemy.dialects.postgresql import JSONB

class CampaignRun(SQLModel, table=True):
    __tablename__ = "campaign_run"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    campaign_id: uuid.UUID = Field(foreign_key="campaign.id", index=True)
    apify_run_id: str = Field(index=True)
    status: str = Field(default="processing") # processing, completed, failed
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    result_data: Dict[str, Any] = Field(default={}, sa_type=JSONB)
    meta_data: Dict[str, Any] = Field(default={}, sa_type=JSONB) # Extra info like actor_id, logs
