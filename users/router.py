from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from backend.database import get_session
from backend.auth.dependencies import get_current_user
from backend.users.models import User, Organization
from pydantic import BaseModel

router = APIRouter(prefix="/api/org", tags=["organization"])

class OrgUpdate(BaseModel):
    industry: str | None = None
    business_model: str | None = None
    stage: str | None = None

@router.patch("/profile", response_model=Organization)
async def update_org_profile(
    org_update: OrgUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user.current_org_id:
        raise HTTPException(status_code=400, detail="User has no organization")
        
    statement = select(Organization).where(Organization.id == current_user.current_org_id)
    org = session.exec(statement).first()
    
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
        
    if org_update.industry:
        org.industry = org_update.industry
    if org_update.business_model:
        org.business_model = org_update.business_model
    if org_update.stage:
        org.stage = org_update.stage
        
    session.add(org)
    session.commit()
    session.refresh(org)
    return org

@router.get("/", response_model=Organization)
async def get_org(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user.current_org_id:
        raise HTTPException(status_code=400, detail="User has no organization")
        
    org = session.get(Organization, current_user.current_org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org
