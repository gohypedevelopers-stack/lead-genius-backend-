"""
Security utilities for Lead Genius API.
Consolidated JWT and password handling.
"""
from datetime import datetime, timedelta
from typing import Optional, Literal
import uuid
import secrets

import jwt
import bcrypt

from backend.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'), 
        hashed_password.encode('utf-8')
    )


def get_password_hash(password: str) -> str:
    """Hash a password."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')



# Token types
TokenType = Literal["access", "refresh"]


def create_token(
    data: dict, 
    token_type: TokenType = "access",
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT token.
    
    Args:
        data: Payload data (should include user_id, org_id)
        token_type: 'access' or 'refresh'
        expires_delta: Custom expiration time
    
    Returns:
        Encoded JWT string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    elif token_type == "refresh":
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": token_type,
        "jti": str(uuid.uuid4())  # Unique token ID for revocation
    })
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create an access token."""
    return create_token(data, token_type="access", expires_delta=expires_delta)


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a refresh token."""
    return create_token(data, token_type="refresh", expires_delta=expires_delta)


def decode_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT token.
    
    Returns:
        Decoded payload dict or None if invalid
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def verify_token(token: str, token_type: TokenType = "access") -> Optional[dict]:
    """
    Verify a token and check its type.
    
    Returns:
        Decoded payload if valid and correct type, None otherwise
    """
    payload = decode_token(token)
    if payload and payload.get("type") == token_type:
        return payload
    return None


def generate_secure_token(length: int = 32) -> str:
    """Generate a secure random token for password reset, email verification, etc."""
    return secrets.token_urlsafe(length)


def generate_verification_code(length: int = 6) -> str:
    """Generate a numeric verification code."""
    return ''.join(secrets.choice('0123456789') for _ in range(length))
