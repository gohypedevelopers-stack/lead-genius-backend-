from fastapi import APIRouter, Depends
from typing import List, Dict, Any
from sqlmodel import Session, select, func
from backend.database import get_session
from backend.auth.dependencies import get_current_user
from backend.users.models import User
from backend.leads.models import Lead
from backend.campaigns.models import Campaign
from backend.activity.models import ActivityLog

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/stats")
async def get_stats(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # Total Leads
    total_leads = session.exec(
        select(func.count(Lead.id)).where(Lead.org_id == current_user.current_org_id)
    ).one()
    
    # Qualified Leads (Example logic: score > 80 or status='qualified')
    qualified_leads = session.exec(
        select(func.count(Lead.id)).where(Lead.org_id == current_user.current_org_id, Lead.score >= 80)
    ).one()
    
    # Active Campaigns
    active_campaigns = session.exec(
        select(func.count(Campaign.id)).where(Campaign.org_id == current_user.current_org_id, Campaign.status == "active")
    ).one()
    
    return {
        "total_leads": total_leads,
        "qualified_leads": qualified_leads,
        "active_campaigns": active_campaigns,
        "response_rate": "4.2%", # Mock
        "pending_tasks": 8 # Mock
    }

@router.get("/activity", response_model=List[ActivityLog])
async def get_activity(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    statement = select(ActivityLog).where(ActivityLog.org_id == current_user.current_org_id).order_by(ActivityLog.created_at.desc()).limit(10)
    results = session.exec(statement)
    return results.all()

@router.get("/chart")
async def get_chart_data():
    return {
        "labels": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        "data": [38, 62, 24, 55, 32, 70]
    }
