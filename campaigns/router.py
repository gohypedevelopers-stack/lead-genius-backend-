from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlmodel import Session, select
from backend.database import get_session
from backend.auth.dependencies import get_current_user
from backend.users.models import User
from backend.models.campaign import Campaign
from backend.models.lead import Lead

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

    # Trigger Apify if Cloud Scraper is enabled
    settings = campaign.settings or {}
    if settings.get("use_cloud_scraper"):
        from backend.services.apify_service import apify_service
        
        # Determine actor ID (default to LinkedIn Scraper likely)
        # For now using a placeholder or config value. Assuming 'linkedin-post' type maps to a specific actor.
        actor_id = "kfiWxiIPwaRIQAU42" # Default LinkedIn Post Scraper ID or from config
        
        run_input = {
            "startUrls": [{"url": settings.get("url")}],
            "maxItems": settings.get("target_count", 10),
            # Add other filters if needed
        }
        
        result = apify_service.run_actor(actor_id, run_input)
        
        if result["success"]:
            campaign.status = "processing"
            
            # Create CampaignRun
            from backend.campaigns.run_models import CampaignRun
            run_record = CampaignRun(
                campaign_id=campaign.id,
                apify_run_id=result["run_id"],
                status="processing",
                meta_data={"actor_id": result["actor_id"]}
            )
            session.add(run_record)
            
            settings["apify_info"] = {
                "run_id": result["run_id"],
                "actor_id": result["actor_id"],
                "triggered_at": "now"
            }
            campaign.settings = settings
            session.add(campaign)
            session.commit()
        else:
            # Log error but don't fail campaign creation entirely?
            # Or maybe set status to failed
            campaign.status = "failed"
            session.add(campaign)
            session.commit()

    return campaign

@router.get("/", response_model=List[Campaign])
async def list_campaigns(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    statement = select(Campaign).where(Campaign.org_id == current_user.current_org_id)
    results = session.exec(statement)
    return results.all()

@router.get("/{id}/runs")
async def get_campaign_runs(
    id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    from backend.campaigns.run_models import CampaignRun
    # Verify campaign ownership
    statement = select(Campaign).where(Campaign.id == id, Campaign.org_id == current_user.current_org_id)
    campaign = session.exec(statement).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    statement = select(CampaignRun).where(CampaignRun.campaign_id == id).order_by(CampaignRun.created_at.desc())
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
