"""
Activity log repository.
"""
import uuid
from typing import Optional, List
from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.models.activity import ActivityLog
from backend.repositories.base import BaseRepository


class ActivityLogRepository(BaseRepository[ActivityLog]):
    """Repository for ActivityLog operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(ActivityLog, session)
    
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
        """Create an activity log entry."""
        activity = ActivityLog(
            org_id=org_id,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            meta_data=meta_data or {},
            ip_address=ip_address,
            user_agent=user_agent
        )
        self.session.add(activity)
        await self.session.commit()
        await self.session.refresh(activity)
        return activity
    
    async def get_recent(self, org_id: uuid.UUID, limit: int = 10) -> List[ActivityLog]:
        """Get recent activity for an organization."""
        query = select(ActivityLog).where(
            ActivityLog.org_id == org_id
        ).order_by(ActivityLog.created_at.desc()).limit(limit)
        result = await self.session.exec(query)
        return result.all()
    
    async def get_by_entity(
        self, 
        org_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID,
        limit: int = 50
    ) -> List[ActivityLog]:
        """Get activity for a specific entity."""
        query = select(ActivityLog).where(
            ActivityLog.org_id == org_id,
            ActivityLog.entity_type == entity_type,
            ActivityLog.entity_id == entity_id
        ).order_by(ActivityLog.created_at.desc()).limit(limit)
        result = await self.session.exec(query)
        return result.all()
    
    async def get_by_actor(
        self,
        org_id: uuid.UUID,
        actor_id: uuid.UUID,
        limit: int = 50
    ) -> List[ActivityLog]:
        """Get activity by a specific user."""
        query = select(ActivityLog).where(
            ActivityLog.org_id == org_id,
            ActivityLog.actor_id == actor_id
        ).order_by(ActivityLog.created_at.desc()).limit(limit)
        result = await self.session.exec(query)
        return result.all()
