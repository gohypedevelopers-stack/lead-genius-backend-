"""
User service - user profile operations.
"""
import uuid
from typing import Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from backend.core.exceptions import raise_not_found, raise_forbidden
from backend.repositories.user_repo import UserRepository, OrganizationRepository
from backend.repositories.activity_repo import ActivityLogRepository
from backend.models.user import User, Organization
from backend.models.activity import Actions


class UserService:
    """Service for user operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.org_repo = OrganizationRepository(session)
        self.activity_repo = ActivityLogRepository(session)
    
    async def get_profile(self, user_id: uuid.UUID) -> User:
        """Get user profile."""
        user = await self.user_repo.get(user_id)
        if not user:
            raise_not_found("User", str(user_id))
        return user
    
    async def update_profile(
        self, 
        user_id: uuid.UUID, 
        full_name: Optional[str] = None,
        avatar_url: Optional[str] = None
    ) -> User:
        """Update user profile."""
        update_data = {}
        if full_name is not None:
            update_data["full_name"] = full_name
        if avatar_url is not None:
            update_data["avatar_url"] = avatar_url
        
        user = await self.user_repo.update(user_id, update_data)
        if not user:
            raise_not_found("User", str(user_id))
        
        # Log activity
        await self.activity_repo.log(
            org_id=user.current_org_id,
            actor_id=user_id,
            action=Actions.USER_UPDATED,
            entity_type="user",
            entity_id=user_id,
            description="Profile updated"
        )
        
        return user
    
    async def get_organization(self, org_id: uuid.UUID) -> Organization:
        """Get organization details."""
        org = await self.org_repo.get(org_id)
        if not org:
            raise_not_found("Organization", str(org_id))
        return org
    
    async def update_organization(
        self, 
        org_id: uuid.UUID, 
        user_id: uuid.UUID,
        update_data: dict
    ) -> Organization:
        """Update organization profile."""
        # Verify user belongs to org (already done in dependency, but double-check)
        user = await self.user_repo.get(user_id)
        if not user or user.current_org_id != org_id:
            raise_forbidden("You don't have permission to update this organization")
        
        org = await self.org_repo.update(org_id, update_data)
        if not org:
            raise_not_found("Organization", str(org_id))
        
        return org
