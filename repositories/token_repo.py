"""
Token repositories for auth tokens.
"""
import uuid
from typing import Optional
from datetime import datetime, timedelta

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.models.token import RefreshToken, PasswordResetToken, EmailVerificationToken
from backend.repositories.base import BaseRepository
from backend.config import settings
from backend.core.security import generate_secure_token


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    """Repository for RefreshToken operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(RefreshToken, session)
    
    async def create_token(
        self, 
        user_id: uuid.UUID, 
        jti: str,
        token: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> RefreshToken:
        """Create a new refresh token."""
        expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        refresh_token = RefreshToken(
            user_id=user_id,
            token=token,
            jti=jti,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address
        )
        self.session.add(refresh_token)
        await self.session.commit()
        await self.session.refresh(refresh_token)
        return refresh_token
    
    async def get_by_jti(self, jti: str) -> Optional[RefreshToken]:
        """Get refresh token by JWT ID."""
        query = select(RefreshToken).where(RefreshToken.jti == jti)
        result = await self.session.exec(query)
        return result.first()
    
    async def get_by_token(self, token: str) -> Optional[RefreshToken]:
        """Get refresh token by token string."""
        query = select(RefreshToken).where(RefreshToken.token == token)
        result = await self.session.exec(query)
        return result.first()
    
    async def revoke(self, token_id: uuid.UUID) -> bool:
        """Revoke a refresh token."""
        token = await self.get(token_id)
        if token:
            token.revoked = True
            token.revoked_at = datetime.utcnow()
            self.session.add(token)
            await self.session.commit()
            return True
        return False
    
    async def revoke_all_for_user(self, user_id: uuid.UUID) -> int:
        """Revoke all refresh tokens for a user."""
        query = select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked == False
        )
        result = await self.session.exec(query)
        tokens = result.all()
        
        count = 0
        for token in tokens:
            token.revoked = True
            token.revoked_at = datetime.utcnow()
            self.session.add(token)
            count += 1
        
        await self.session.commit()
        return count
    
    async def is_valid(self, jti: str) -> bool:
        """Check if a refresh token is valid (not revoked, not expired)."""
        token = await self.get_by_jti(jti)
        if not token:
            return False
        if token.revoked:
            return False
        if token.expires_at < datetime.utcnow():
            return False
        return True


class PasswordResetTokenRepository(BaseRepository[PasswordResetToken]):
    """Repository for PasswordResetToken operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(PasswordResetToken, session)
    
    async def create_token(self, user_id: uuid.UUID) -> PasswordResetToken:
        """Create a new password reset token."""
        token = generate_secure_token()
        expires_at = datetime.utcnow() + timedelta(hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS)
        
        reset_token = PasswordResetToken(
            user_id=user_id,
            token=token,
            expires_at=expires_at
        )
        self.session.add(reset_token)
        await self.session.commit()
        await self.session.refresh(reset_token)
        return reset_token
    
    async def get_valid_token(self, token: str) -> Optional[PasswordResetToken]:
        """Get a valid (not used, not expired) password reset token."""
        query = select(PasswordResetToken).where(
            PasswordResetToken.token == token,
            PasswordResetToken.used == False,
            PasswordResetToken.expires_at > datetime.utcnow()
        )
        result = await self.session.exec(query)
        return result.first()
    
    async def mark_used(self, token_id: uuid.UUID) -> bool:
        """Mark a token as used."""
        token = await self.get(token_id)
        if token:
            token.used = True
            token.used_at = datetime.utcnow()
            self.session.add(token)
            await self.session.commit()
            return True
        return False


class EmailVerificationTokenRepository(BaseRepository[EmailVerificationToken]):
    """Repository for EmailVerificationToken operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(EmailVerificationToken, session)
    
    async def create_token(self, user_id: uuid.UUID, email: str) -> EmailVerificationToken:
        """Create a new email verification token."""
        token = generate_secure_token()
        expires_at = datetime.utcnow() + timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS)
        
        verification_token = EmailVerificationToken(
            user_id=user_id,
            email=email,
            token=token,
            expires_at=expires_at
        )
        self.session.add(verification_token)
        await self.session.commit()
        await self.session.refresh(verification_token)
        return verification_token
    
    async def get_valid_token(self, token: str) -> Optional[EmailVerificationToken]:
        """Get a valid (not verified, not expired) email verification token."""
        query = select(EmailVerificationToken).where(
            EmailVerificationToken.token == token,
            EmailVerificationToken.verified == False,
            EmailVerificationToken.expires_at > datetime.utcnow()
        )
        result = await self.session.exec(query)
        return result.first()
    
    async def mark_verified(self, token_id: uuid.UUID) -> bool:
        """Mark a token as verified."""
        token = await self.get(token_id)
        if token:
            token.verified = True
            token.verified_at = datetime.utcnow()
            self.session.add(token)
            await self.session.commit()
            return True
        return False
