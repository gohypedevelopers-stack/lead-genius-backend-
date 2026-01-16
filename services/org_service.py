"""
Organization service - handles multi-org operations.
"""
import uuid
from typing import Optional, List
from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.config import settings
from backend.core.security import create_access_token
from backend.core.exceptions import (
    raise_not_found, 
    raise_forbidden, 
    raise_already_exists,
    raise_validation_error
)
from backend.repositories.user_repo import (
    UserRepository, 
    OrganizationRepository, 
    OrganizationMemberRepository
)
from backend.models.user import User, Organization, OrganizationMember


class OrganizationService:
    """Service for organization management."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.org_repo = OrganizationRepository(session)
        self.member_repo = OrganizationMemberRepository(session)
    
    async def create_organization(
        self,
        user: User,
        name: str,
        domain: Optional[str] = None,
        industry: Optional[str] = None,
        business_model: Optional[str] = None
    ) -> dict:
        """
        Create a new organization and add user as owner.
        
        Returns:
            dict with org details and membership
        """
        # Check for duplicate domain if provided
        if domain:
            existing = await self.org_repo.get_by_domain(domain)
            if existing:
                raise_already_exists("Organization", "domain", domain)
        
        # Create organization
        org = Organization(
            name=name,
            domain=domain,
            industry=industry,
            business_model=business_model
        )
        self.session.add(org)
        await self.session.flush()
        
        # Create membership as owner
        membership = OrganizationMember(
            user_id=user.id,
            org_id=org.id,
            role="owner"
        )
        self.session.add(membership)
        
        await self.session.commit()
        await self.session.refresh(org)
        await self.session.refresh(membership)
        
        return {
            "organization": {
                "id": str(org.id),
                "name": org.name,
                "domain": org.domain,
                "industry": org.industry
            },
            "membership": {
                "role": membership.role,
                "joined_at": membership.joined_at.isoformat()
            },
            "message": f"Organization '{name}' created successfully"
        }
    
    async def get_user_organizations(self, user_id: uuid.UUID) -> List[dict]:
        """Get all organizations user belongs to."""
        memberships = await self.member_repo.get_user_memberships(user_id)
        
        result = []
        for membership in memberships:
            org = await self.org_repo.get(membership.org_id)
            if org:
                result.append({
                    "id": str(org.id),
                    "name": org.name,
                    "domain": org.domain,
                    "industry": org.industry,
                    "role": membership.role,
                    "joined_at": membership.joined_at.isoformat(),
                    "is_active": membership.is_active
                })
        
        return result
    
    async def switch_organization(self, user: User, org_id: uuid.UUID) -> dict:
        """
        Switch user's active organization.
        
        Returns:
            New access token with updated org_id
        """
        # Verify user is member of org
        is_member = await self.member_repo.is_member(user.id, org_id)
        if not is_member:
            raise_forbidden("You are not a member of this organization")
        
        # Get org details
        org = await self.org_repo.get(org_id)
        if not org:
            raise_not_found("Organization")
        
        # Update user's current org
        await self.user_repo.switch_org(user.id, org_id)
        
        # Generate new access token with new org
        token_data = {
            "sub": user.email,
            "user_id": str(user.id),
            "org_id": str(org_id)
        }
        new_access_token = create_access_token(token_data)
        
        return {
            "message": f"Switched to organization '{org.name}'",
            "organization": {
                "id": str(org.id),
                "name": org.name
            },
            "access_token": new_access_token,
            "token_type": "bearer"
        }
    
    async def get_organization_members(
        self, 
        org_id: uuid.UUID, 
        user: User
    ) -> List[dict]:
        """Get all members of an organization."""
        # Verify user is member of org
        is_member = await self.member_repo.is_member(user.id, org_id)
        if not is_member:
            raise_forbidden("You are not a member of this organization")
        
        memberships = await self.member_repo.get_org_members(org_id)
        
        result = []
        for membership in memberships:
            member = await self.user_repo.get(membership.user_id)
            if member:
                result.append({
                    "id": str(membership.id),
                    "user_id": str(member.id),
                    "email": member.email,
                    "full_name": member.full_name,
                    "role": membership.role,
                    "joined_at": membership.joined_at.isoformat(),
                    "is_active": membership.is_active
                })
        
        return result
    
    async def invite_user_to_org(
        self,
        org_id: uuid.UUID,
        inviter: User,
        invitee_email: str,
        role: str = "member"
    ) -> dict:
        """
        Invite an existing user to an organization.
        
        Note: For MVP, user must already be registered.
        Future enhancement: send invite email for non-existing users.
        """
        # Check inviter has permission
        is_admin = await self.member_repo.is_admin(inviter.id, org_id)
        if not is_admin:
            raise_forbidden("Only admins can invite members")
        
        # Validate role
        valid_roles = ["admin", "member", "viewer"]
        if role not in valid_roles:
            raise_validation_error(f"Invalid role. Must be one of: {valid_roles}")
        
        # Find invitee
        invitee = await self.user_repo.get_by_email(invitee_email)
        if not invitee:
            raise_not_found("User", f"No user found with email {invitee_email}")
        
        # Check if already member
        existing = await self.member_repo.get_membership(invitee.id, org_id)
        if existing:
            if existing.is_active:
                raise_already_exists("Member", "email", invitee_email)
            else:
                # Reactivate existing membership
                existing.is_active = True
                existing.role = role
                self.session.add(existing)
                await self.session.commit()
                return {"message": f"User {invitee_email} re-added to organization"}
        
        # Create membership
        membership = await self.member_repo.create_membership(
            user_id=invitee.id,
            org_id=org_id,
            role=role,
            invited_by=inviter.id
        )
        
        org = await self.org_repo.get(org_id)
        
        return {
            "message": f"User {invitee_email} invited to {org.name} as {role}",
            "membership_id": str(membership.id)
        }
    
    async def update_member_role(
        self,
        org_id: uuid.UUID,
        admin_user: User,
        target_user_id: uuid.UUID,
        new_role: str
    ) -> dict:
        """Update a member's role in the organization."""
        # Check requester has permission
        is_admin = await self.member_repo.is_admin(admin_user.id, org_id)
        if not is_admin:
            raise_forbidden("Only admins can update roles")
        
        # Get target membership
        membership = await self.member_repo.get_membership(target_user_id, org_id)
        if not membership:
            raise_not_found("Membership")
        
        # Can't change owner role (must transfer ownership separately)
        if membership.role == "owner":
            raise_forbidden("Cannot change owner role. Transfer ownership first.")
        
        # Validate role
        valid_roles = ["admin", "member", "viewer"]
        if new_role not in valid_roles:
            raise_validation_error(f"Invalid role. Must be one of: {valid_roles}")
        
        # Update role
        await self.member_repo.update_role(membership.id, new_role)
        
        return {"message": f"Role updated to {new_role}"}
    
    async def remove_member(
        self,
        org_id: uuid.UUID,
        admin_user: User,
        target_user_id: uuid.UUID
    ) -> dict:
        """Remove a member from the organization."""
        # Check requester has permission
        is_admin = await self.member_repo.is_admin(admin_user.id, org_id)
        if not is_admin:
            raise_forbidden("Only admins can remove members")
        
        # Get target membership
        membership = await self.member_repo.get_membership(target_user_id, org_id)
        if not membership:
            raise_not_found("Membership")
        
        # Can't remove owner
        if membership.role == "owner":
            raise_forbidden("Cannot remove owner from organization")
        
        # Deactivate membership (soft delete)
        await self.member_repo.deactivate_membership(membership.id)
        
        return {"message": "Member removed from organization"}
    
    async def leave_organization(
        self,
        user: User,
        org_id: uuid.UUID
    ) -> dict:
        """User leaves an organization."""
        membership = await self.member_repo.get_membership(user.id, org_id)
        if not membership:
            raise_not_found("Membership")
        
        # Owner can't leave (must transfer ownership first)
        if membership.role == "owner":
            raise_forbidden("Owner cannot leave. Transfer ownership first.")
        
        # Deactivate membership
        await self.member_repo.deactivate_membership(membership.id)
        
        # If this was current org, switch to another
        if user.current_org_id == org_id:
            other_memberships = await self.member_repo.get_user_memberships(user.id)
            if other_memberships:
                await self.user_repo.switch_org(user.id, other_memberships[0].org_id)
            else:
                await self.user_repo.switch_org(user.id, None)
        
        return {"message": "You have left the organization"}
