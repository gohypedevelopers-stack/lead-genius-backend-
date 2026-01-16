import uuid
from typing import Optional
from sqlmodel import SQLModel, Field

class OutreachMessage(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    lead_id: uuid.UUID = Field(foreign_key="lead.id")
    channel: str = Field(default="linkedin")
    message: str
    status: str = Field(default="pending") # pending, sent, failed
