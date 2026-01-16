"""
Activity service - activity logging.
"""
import uuid
from typing import Optional, List

from sqlmodel.ext.asyncio.session import AsyncSession

from backend.repositories.activity_repo import ActivityLogRepository
from backend.models.activity import ActivityLog


class ActivityService:
    """Service for activity logging."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.activity_repo = ActivityLogRepository(session)
    
    async def log(
        self,
        org_id: uuid.UUID,
        action: str,
        entity_type: str,
        entity_id: Optional[uuid.UUID] = None,
        actor_id: Optional[uuid.UUID] = None,
        description: Optional[str] = None,
        meta_data: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> ActivityLog:
        """Log an activity."""
        return await self.activity_repo.log(
            org_id=org_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            description=description,
            meta_data=meta_data,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    async def get_recent(self, org_id: uuid.UUID, limit: int = 10) -> List[ActivityLog]:
        """Get recent activity for dashboard."""
        return await self.activity_repo.get_recent(org_id, limit)
    
    async def get_by_entity(
        self,
        org_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID,
        limit: int = 50
    ) -> List[ActivityLog]:
        """Get activity for a specific entity."""
        return await self.activity_repo.get_by_entity(org_id, entity_type, entity_id, limit)
