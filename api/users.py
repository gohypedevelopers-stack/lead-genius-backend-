"""
User and Organization API routes.
"""
from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.database import get_session
from backend.services.user_service import UserService
from backend.schemas.user import UserResponse, UserUpdate, OrganizationResponse, OrganizationUpdate
from backend.api.deps import get_current_user
from backend.models.user import User, OrganizationMember

router = APIRouter(tags=["users"])


# User endpoints
@router.get("/api/users/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get current user profile with role in current organization."""
    # Get role from OrganizationMember
    role = None
    if current_user.current_org_id:
        query = select(OrganizationMember).where(
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.org_id == current_user.current_org_id
        )
        result = await session.exec(query)
        membership = result.first()
        if membership:
            role = membership.role
    
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        avatar_url=current_user.avatar_url,
        is_verified=current_user.is_verified,
        current_org_id=current_user.current_org_id,
        role=role,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at
    )


@router.patch("/api/users/me", response_model=UserResponse)
async def update_current_user_profile(
    update_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Update current user profile."""
    user_service = UserService(session)
    updated_user = await user_service.update_profile(
        current_user.id,
        full_name=update_data.full_name,
        avatar_url=update_data.avatar_url
    )
    
    # Get role
    role = None
    if updated_user.current_org_id:
        query = select(OrganizationMember).where(
            OrganizationMember.user_id == updated_user.id,
            OrganizationMember.org_id == updated_user.current_org_id
        )
        result = await session.exec(query)
        membership = result.first()
        if membership:
            role = membership.role
    
    return UserResponse(
        id=updated_user.id,
        email=updated_user.email,
        full_name=updated_user.full_name,
        avatar_url=updated_user.avatar_url,
        is_verified=updated_user.is_verified,
        current_org_id=updated_user.current_org_id,
        role=role,
        created_at=updated_user.created_at,
        last_login_at=updated_user.last_login_at
    )


# Organization endpoints
@router.get("/api/org/", response_model=OrganizationResponse)
async def get_organization(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get current user's organization."""
    user_service = UserService(session)
    return await user_service.get_organization(current_user.current_org_id)


@router.patch("/api/org/profile", response_model=OrganizationResponse)
async def update_organization_profile(
    update_data: OrganizationUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Update organization profile."""
    user_service = UserService(session)
    return await user_service.update_organization(
        current_user.current_org_id,
        current_user.id,
        update_data.model_dump(exclude_unset=True)
    )
