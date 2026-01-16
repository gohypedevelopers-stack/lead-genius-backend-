from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from backend.database import get_session
from backend.users.models import User, Organization
from backend.auth.utils import verify_password, create_access_token, get_password_hash
import uuid

router = APIRouter(tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")

@router.post("/register")
async def register(
    email: str, 
    password: str, 
    org_name: str, 
    session: AsyncSession = Depends(get_session)
):
    # Check if user exists
    result = await session.exec(select(User).where(User.email == email))
    if result.first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create Org
    org = Organization(name=org_name)
    session.add(org)
    await session.commit()
    await session.refresh(org)
    
    # Create User
    user = User(
        email=email, 
        password_hash=get_password_hash(password),
        org_id=org.id
    )
    session.add(user)
    await session.commit()
    return {"message": "User registered successfully"}

@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(User).where(User.email == form_data.username))
    user = result.first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    access_token = create_access_token(
        data={"sub": user.email, "user_id": str(user.id), "org_id": str(user.current_org_id)}
    )
    return {"access_token": access_token, "token_type": "bearer"}
