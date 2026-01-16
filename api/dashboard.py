"""
Dashboard API routes.
"""
from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import func, select
from datetime import datetime, timedelta

from backend.database import get_session
from backend.services.activity_service import ActivityService
from backend.services.lead_service import LeadService
from backend.repositories.campaign_repo import CampaignRepository
from backend.repositories.outreach_repo import OutreachMessageRepository
from backend.api.deps import get_current_user
from backend.models.user import User
from backend.models.lead import Lead
from backend.models.campaign import Campaign

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get dashboard statistics."""
    org_id = current_user.current_org_id
    
    # Lead stats
    lead_service = LeadService(session)
    lead_stats = await lead_service.get_stats(org_id)
    
    # Campaign stats
    campaign_repo = CampaignRepository(session)
    active_campaigns = await campaign_repo.count_by_status(org_id, "active")
    
    # Outreach stats
    outreach_repo = OutreachMessageRepository(session)
    message_counts = await outreach_repo.count_by_status(org_id)
    
    # Calculate response rate
    sent = message_counts.get("sent", 0) + message_counts.get("delivered", 0)
    replied = message_counts.get("replied", 0)
    response_rate = f"{(replied / sent * 100):.1f}%" if sent > 0 else "0%"
    
    return {
        "total_leads": lead_stats["total"],
        "qualified_leads": lead_stats["qualified"],
        "active_campaigns": active_campaigns,
        "response_rate": response_rate,
        "pending_tasks": message_counts.get("pending", 0) + message_counts.get("scheduled", 0),
        "lead_stats": lead_stats,
        "message_stats": message_counts
    }


@router.get("/activity")
async def get_activity(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get recent activity."""
    activity_service = ActivityService(session)
    activities = await activity_service.get_recent(current_user.current_org_id, limit)
    return {"items": activities, "total": len(activities)}


@router.get("/chart")
async def get_chart_data(
    days: int = Query(7, ge=1, le=30),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get chart data for leads over time."""
    org_id = current_user.current_org_id
    
    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Get leads grouped by date
    query = select(
        func.date(Lead.created_at).label("date"),
        func.count(Lead.id).label("count")
    ).where(
        Lead.org_id == org_id,
        Lead.created_at >= start_date
    ).group_by(
        func.date(Lead.created_at)
    ).order_by(
        func.date(Lead.created_at)
    )
    
    result = await session.exec(query)
    rows = result.all()
    
    # Build labels and data
    labels = []
    data = []
    
    for i in range(days):
        date = start_date + timedelta(days=i)
        date_str = date.strftime("%a")  # Mon, Tue, etc.
        labels.append(date_str)
        
        # Find count for this date
        count = 0
        for row in rows:
            if row.date == date.date():
                count = row.count
                break
        data.append(count)
    
    return {
        "labels": labels,
        "data": data,
        "total": sum(data)
    }
