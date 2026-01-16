"""
Organization API routes.
Handles multi-org operations: create, list, switch, manage members.
"""
import uuid
from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.database import get_session
from backend.services.org_service import OrganizationService
from backend.schemas.organization import (
    CreateOrganizationRequest,
    InviteUserRequest,
    UpdateMemberRoleRequest,
    UpdateOrganizationRequest
)
from backend.schemas.common import MessageResponse
from backend.api.deps import get_current_user
from backend.models.user import User

router = APIRouter(prefix="/api/organizations", tags=["organizations"])


@router.post("/")
async def create_organization(
    request: CreateOrganizationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Create a new organization.
    Current user becomes the owner of the new organization.
    """
    org_service = OrganizationService(session)
    return await org_service.create_organization(
        user=current_user,
        name=request.name,
        domain=request.domain,
        industry=request.industry,
        business_model=request.business_model
    )


@router.get("/")
async def list_my_organizations(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    List all organizations the current user belongs to.
    """
    org_service = OrganizationService(session)
    orgs = await org_service.get_user_organizations(current_user.id)
    return {
        "organizations": orgs,
        "count": len(orgs),
        "current_org_id": str(current_user.current_org_id) if current_user.current_org_id else None
    }


@router.post("/switch/{org_id}")
async def switch_organization(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Switch to a different organization.
    Returns a new access token with the new org_id.
    """
    org_service = OrganizationService(session)
    return await org_service.switch_organization(current_user, org_id)


@router.get("/{org_id}/members")
async def list_organization_members(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    List all members of an organization.
    Requires user to be a member of the organization.
    """
    org_service = OrganizationService(session)
    members = await org_service.get_organization_members(org_id, current_user)
    return {
        "members": members,
        "count": len(members)
    }


@router.post("/{org_id}/invite")
async def invite_user(
    org_id: uuid.UUID,
    request: InviteUserRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Invite a user to the organization.
    Requires admin or owner role.
    """
    org_service = OrganizationService(session)
    return await org_service.invite_user_to_org(
        org_id=org_id,
        inviter=current_user,
        invitee_email=request.email,
        role=request.role
    )


@router.patch("/{org_id}/members/{user_id}")
async def update_member_role(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    request: UpdateMemberRoleRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Update a member's role in the organization.
    Requires admin or owner role.
    """
    org_service = OrganizationService(session)
    return await org_service.update_member_role(
        org_id=org_id,
        admin_user=current_user,
        target_user_id=user_id,
        new_role=request.role
    )


@router.delete("/{org_id}/members/{user_id}")
async def remove_member(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Remove a member from the organization.
    Requires admin or owner role.
    """
    org_service = OrganizationService(session)
    return await org_service.remove_member(
        org_id=org_id,
        admin_user=current_user,
        target_user_id=user_id
    )


@router.post("/{org_id}/leave")
async def leave_organization(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Leave an organization.
    Owner cannot leave - must transfer ownership first.
    """
    org_service = OrganizationService(session)
    return await org_service.leave_organization(current_user, org_id)
