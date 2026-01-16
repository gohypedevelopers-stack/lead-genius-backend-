"""
Extension API routes.
Endpoints for Chrome extension to fetch and update outreach messages.
"""
import uuid
import secrets
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from pydantic import BaseModel

from backend.database import get_session
from backend.api.deps import get_current_user
from backend.models.user import User
from backend.models.outreach import OutreachMessage
from backend.models.lead import Lead


router = APIRouter(prefix="/api/extension", tags=["extension"])


# =============================================================================
# SCHEMAS
# =============================================================================

class ExtensionTokenResponse(BaseModel):
    """Extension authentication token."""
    token: str
    expires_in: int
    user_email: str
    org_id: str


class QueuedMessage(BaseModel):
    """Message in the extension queue."""
    id: str
    lead_name: str
    lead_company: Optional[str]
    linkedin_url: str
    message: str
    channel: str
    template_name: Optional[str]
    created_at: str


class MessageQueueResponse(BaseModel):
    """List of queued messages for extension."""
    messages: List[QueuedMessage]
    count: int


class StatusUpdateRequest(BaseModel):
    """Request to update message status from extension."""
    status: str  # sending, sent, failed
    error_message: Optional[str] = None
    linkedin_message_id: Optional[str] = None
    extension_session_id: Optional[str] = None


class BatchStatusUpdate(BaseModel):
    """Batch update multiple messages."""
    message_id: str
    status: str
    error_message: Optional[str] = None


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/auth", response_model=ExtensionTokenResponse)
async def generate_extension_token(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Generate a token for the Chrome extension.
    Extension uses this token to authenticate API calls.
    
    Token is valid for 30 days.
    """
    # Generate a secure token
    token = secrets.token_urlsafe(32)
    
    # In production, store this in database with expiration
    # For now, we'll use the access token pattern
    
    return ExtensionTokenResponse(
        token=token,
        expires_in=30 * 24 * 60 * 60,  # 30 days in seconds
        user_email=current_user.email,
        org_id=str(current_user.current_org_id)
    )


@router.get("/queue", response_model=MessageQueueResponse)
async def get_message_queue(
    limit: int = Query(default=20, le=100),
    channel: str = Query(default="linkedin"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Get pending messages for the extension to send.
    Returns messages with status 'queued' or 'pending' that are ready to send.
    """
    # Query messages that are queued for extension sending
    query = select(OutreachMessage).where(
        OutreachMessage.org_id == current_user.current_org_id,
        OutreachMessage.channel == channel,
        OutreachMessage.status.in_(["pending", "queued"]),
        OutreachMessage.send_method == "extension"
    ).order_by(OutreachMessage.created_at.asc()).limit(limit)
    
    result = await session.exec(query)
    messages = result.all()
    
    # Enrich with lead data
    queued_messages = []
    for msg in messages:
        # Get lead info
        lead = await session.get(Lead, msg.lead_id)
        if lead:
            queued_messages.append(QueuedMessage(
                id=str(msg.id),
                lead_name=lead.name,
                lead_company=lead.company,
                linkedin_url=lead.linkedin_url or msg.linkedin_profile_url or "",
                message=msg.message,
                channel=msg.channel,
                template_name=None,  # Could join with template
                created_at=msg.created_at.isoformat()
            ))
    
    return MessageQueueResponse(
        messages=queued_messages,
        count=len(queued_messages)
    )


@router.post("/messages/{message_id}/status")
async def update_message_status(
    message_id: uuid.UUID,
    request: StatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Update message status from extension.
    Called when extension sends or fails to send a message.
    """
    # Get message
    message = await session.get(OutreachMessage, message_id)
    if not message:
        return {"error": "Message not found"}
    
    # Verify ownership
    if message.org_id != current_user.current_org_id:
        return {"error": "Access denied"}
    
    # Update status
    message.status = request.status
    message.updated_at = datetime.utcnow()
    
    if request.status == "sent":
        message.sent_at = datetime.utcnow()
    
    if request.error_message:
        message.error_message = request.error_message
        message.retry_count += 1
    
    if request.linkedin_message_id:
        message.linkedin_message_id = request.linkedin_message_id
    
    if request.extension_session_id:
        message.extension_session_id = request.extension_session_id
    
    session.add(message)
    await session.commit()
    
    return {
        "message": f"Status updated to {request.status}",
        "message_id": str(message_id)
    }


@router.post("/messages/batch-status")
async def batch_update_status(
    updates: List[BatchStatusUpdate],
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Batch update multiple message statuses.
    Useful when extension sends multiple messages.
    """
    updated = 0
    errors = []
    
    for update in updates:
        try:
            message = await session.get(OutreachMessage, uuid.UUID(update.message_id))
            if message and message.org_id == current_user.current_org_id:
                message.status = update.status
                message.updated_at = datetime.utcnow()
                if update.status == "sent":
                    message.sent_at = datetime.utcnow()
                if update.error_message:
                    message.error_message = update.error_message
                session.add(message)
                updated += 1
            else:
                errors.append(f"Message {update.message_id} not found or access denied")
        except Exception as e:
            errors.append(f"Error updating {update.message_id}: {str(e)}")
    
    await session.commit()
    
    return {
        "updated": updated,
        "total": len(updates),
        "errors": errors if errors else None
    }


@router.post("/messages/{message_id}/queue")
async def queue_message_for_extension(
    message_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Queue a message for extension sending.
    Changes send_method to 'extension' and status to 'queued'.
    """
    message = await session.get(OutreachMessage, message_id)
    if not message:
        return {"error": "Message not found"}
    
    if message.org_id != current_user.current_org_id:
        return {"error": "Access denied"}
    
    message.send_method = "extension"
    message.status = "queued"
    message.updated_at = datetime.utcnow()
    
    session.add(message)
    await session.commit()
    
    return {
        "message": "Message queued for extension",
        "message_id": str(message_id)
    }


@router.get("/stats")
async def get_extension_stats(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Get extension sending statistics.
    """
    # Count messages by status for extension
    from sqlalchemy import func
    
    query = select(
        OutreachMessage.status,
        func.count(OutreachMessage.id)
    ).where(
        OutreachMessage.org_id == current_user.current_org_id,
        OutreachMessage.send_method == "extension"
    ).group_by(OutreachMessage.status)
    
    result = await session.exec(query)
    stats = {row[0]: row[1] for row in result.all()}
    
    return {
        "queued": stats.get("queued", 0),
        "sending": stats.get("sending", 0),
        "sent": stats.get("sent", 0),
        "failed": stats.get("failed", 0),
        "total": sum(stats.values())
    }
