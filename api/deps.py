"""
API dependencies - shared across all routes.
"""
import uuid
from typing import Optional

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.database import get_session
from backend.config import settings
from backend.core.security import verify_token
from backend.core.exceptions import raise_unauthorized
from backend.models.user import User
from backend.repositories.user_repo import UserRepository


oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    session: AsyncSession = Depends(get_session)
) -> User:
    """Get current authenticated user from JWT token."""
    payload = verify_token(token, "access")
    if not payload:
        raise_unauthorized("Could not validate credentials")
    
    user_id = payload.get("user_id")
    if not user_id:
        raise_unauthorized("Could not validate credentials")
    
    user_repo = UserRepository(session)
    user = await user_repo.get(uuid.UUID(user_id))
    
    if not user:
        raise_unauthorized("User not found")
    
    if not user.is_active:
        raise_unauthorized("User account is deactivated")
    
    return user


async def get_current_active_verified_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current user, must be verified."""
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified"
        )
    return current_user


def get_client_info(request: Request) -> dict:
    """Extract client info from request."""
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent")
    }
