"""
User and Organization repositories.
Updated for multi-organization support.
"""
import uuid
from typing import Optional, List
from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.models.user import User, Organization, OrganizationMember
from backend.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        query = select(User).where(User.email == email)
        result = await self.session.exec(query)
        return result.first()
    
    async def create_with_org(
        self, 
        email: str, 
        password_hash: str, 
        org_name: str,
        full_name: Optional[str] = None
    ) -> tuple[User, Organization, OrganizationMember]:
        """Create user with a new organization and membership."""
        # Create organization
        org = Organization(name=org_name)
        self.session.add(org)
        await self.session.flush()  # Get org.id without committing
        
        # Create user with current_org_id set to new org
        user = User(
            email=email,
            password_hash=password_hash,
            current_org_id=org.id,
            full_name=full_name
        )
        self.session.add(user)
        await self.session.flush()  # Get user.id
        
        # Create membership as owner
        membership = OrganizationMember(
            user_id=user.id,
            org_id=org.id,
            role="owner"
        )
        self.session.add(membership)
        
        await self.session.commit()
        await self.session.refresh(org)
        await self.session.refresh(user)
        await self.session.refresh(membership)
        
        return user, org, membership
    
    async def update_last_login(self, user_id: uuid.UUID) -> None:
        """Update user's last login timestamp."""
        user = await self.get(user_id)
        if user:
            user.last_login_at = datetime.utcnow()
            self.session.add(user)
            await self.session.commit()
    
    async def verify_email(self, user_id: uuid.UUID) -> bool:
        """Mark user as verified."""
        user = await self.get(user_id)
        if user:
            user.is_verified = True
            user.updated_at = datetime.utcnow()
            self.session.add(user)
            await self.session.commit()
            return True
        return False
    
    async def update_password(self, user_id: uuid.UUID, password_hash: str) -> bool:
        """Update user's password."""
        user = await self.get(user_id)
        if user:
            user.password_hash = password_hash
            user.updated_at = datetime.utcnow()
            self.session.add(user)
            await self.session.commit()
            return True
        return False
    
    async def switch_org(self, user_id: uuid.UUID, org_id: uuid.UUID) -> bool:
        """Switch user's current active organization."""
        user = await self.get(user_id)
        if user:
            user.current_org_id = org_id
            user.updated_at = datetime.utcnow()
            self.session.add(user)
            await self.session.commit()
            return True
        return False


class OrganizationRepository(BaseRepository[Organization]):
    """Repository for Organization operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Organization, session)
    
    async def get_by_domain(self, domain: str) -> Optional[Organization]:
        """Get organization by domain."""
        query = select(Organization).where(Organization.domain == domain)
        result = await self.session.exec(query)
        return result.first()


class OrganizationMemberRepository(BaseRepository[OrganizationMember]):
    """Repository for OrganizationMember (junction table) operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(OrganizationMember, session)
    
    async def get_membership(
        self, 
        user_id: uuid.UUID, 
        org_id: uuid.UUID
    ) -> Optional[OrganizationMember]:
        """Get specific membership record."""
        query = select(OrganizationMember).where(
            OrganizationMember.user_id == user_id,
            OrganizationMember.org_id == org_id
        )
        result = await self.session.exec(query)
        return result.first()
    
    async def get_user_memberships(
        self, 
        user_id: uuid.UUID, 
        active_only: bool = True
    ) -> List[OrganizationMember]:
        """Get all organizations a user belongs to."""
        query = select(OrganizationMember).where(
            OrganizationMember.user_id == user_id
        )
        if active_only:
            query = query.where(OrganizationMember.is_active == True)
        result = await self.session.exec(query)
        return list(result.all())
    
    async def get_org_members(
        self, 
        org_id: uuid.UUID, 
        active_only: bool = True
    ) -> List[OrganizationMember]:
        """Get all members of an organization."""
        query = select(OrganizationMember).where(
            OrganizationMember.org_id == org_id
        )
        if active_only:
            query = query.where(OrganizationMember.is_active == True)
        result = await self.session.exec(query)
        return list(result.all())
    
    async def create_membership(
        self,
        user_id: uuid.UUID,
        org_id: uuid.UUID,
        role: str = "member",
        invited_by: Optional[uuid.UUID] = None
    ) -> OrganizationMember:
        """Create a new membership."""
        membership = OrganizationMember(
            user_id=user_id,
            org_id=org_id,
            role=role,
            invited_by=invited_by
        )
        self.session.add(membership)
        await self.session.commit()
        await self.session.refresh(membership)
        return membership
    
    async def update_role(
        self, 
        membership_id: uuid.UUID, 
        new_role: str
    ) -> bool:
        """Update member's role in organization."""
        membership = await self.get(membership_id)
        if membership:
            membership.role = new_role
            self.session.add(membership)
            await self.session.commit()
            return True
        return False
    
    async def deactivate_membership(self, membership_id: uuid.UUID) -> bool:
        """Deactivate a membership (soft delete)."""
        membership = await self.get(membership_id)
        if membership:
            membership.is_active = False
            self.session.add(membership)
            await self.session.commit()
            return True
        return False
    
    async def is_member(self, user_id: uuid.UUID, org_id: uuid.UUID) -> bool:
        """Check if user is an active member of organization."""
        membership = await self.get_membership(user_id, org_id)
        return membership is not None and membership.is_active
    
    async def is_admin(self, user_id: uuid.UUID, org_id: uuid.UUID) -> bool:
        """Check if user is admin or owner of organization."""
        membership = await self.get_membership(user_id, org_id)
        return (
            membership is not None and 
            membership.is_active and 
            membership.role in ["owner", "admin"]
        )

