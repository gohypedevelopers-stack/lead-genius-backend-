"""
Persona schemas.
"""
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel


class PersonaCreate(BaseModel):
    """Create a persona/ICP."""
    name: str
    description: Optional[str] = None
    priority: int = 1
    rules_json: Dict[str, Any] = {}
    score_bonus: int = 50
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Enterprise Decision Maker",
                "description": "VP+ level at 500+ companies",
                "priority": 1,
                "rules_json": {
                    "title_keywords": ["vp", "director", "head of"],
                    "company_size_min": 500,
                    "industries": ["technology", "finance"]
                },
                "score_bonus": 60
            }
        }


class PersonaUpdate(BaseModel):
    """Update a persona."""
    name: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = None
    rules_json: Optional[Dict[str, Any]] = None
    score_bonus: Optional[int] = None
    is_active: Optional[bool] = None


class PersonaResponse(BaseModel):
    """Persona response."""
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    description: Optional[str]
    priority: int
    rules_json: Dict[str, Any]
    score_bonus: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PersonaMatchResult(BaseModel):
    """Result of matching a lead against personas."""
    lead_id: uuid.UUID
    matched_personas: list[uuid.UUID]
    total_score_bonus: int
