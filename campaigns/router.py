from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlmodel import Session, select
from backend.database import get_session
from backend.auth.dependencies import get_current_user
from backend.users.models import User
from backend.campaigns.models import Campaign
from backend.leads.models import Lead

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])

@router.post("/", response_model=Campaign)
async def create_campaign(
    campaign: Campaign, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # Ensure org_id matches current user
    if not campaign.org_id:
        campaign.org_id = current_user.current_org_id
        
    if campaign.org_id != current_user.current_org_id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return campaign

@router.get("/", response_model=List[Campaign])
async def list_campaigns(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    statement = select(Campaign).where(Campaign.org_id == current_user.current_org_id)
    results = session.exec(statement)
    return results.all()

@router.post("/{id}/run")
async def run_campaign(
    id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    statement = select(Campaign).where(Campaign.id == id, Campaign.org_id == current_user.current_org_id)
    campaign = session.exec(statement).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    # Mock execution: Create dummy leads
    campaign.status = "processing"
    session.add(campaign)
    session.commit()
    
    # In a real app, this would be a background task
    import random
    
    # Create 3 mock leads
    for i in range(3):
        lead = Lead(
            org_id=campaign.org_id,
            campaign_id=campaign.id,
            name=f"Mock Lead {i+1} from {campaign.name}",
            linkedin_url=f"https://linkedin.com/in/mock-{i}",
            status="new",
            source=campaign.type
        )
        session.add(lead)
        
    campaign.status = "completed"
    campaign.leads_count += 3
    session.add(campaign)
    session.commit()
    
    return {"status": "started", "message": "Campaign execution started"}
