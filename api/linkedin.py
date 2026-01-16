"""
LinkedIn OAuth and API routes.
Supports both user-level (personal) and organization-level (shared) LinkedIn connections.
"""
import uuid
import secrets
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import RedirectResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from pydantic import BaseModel

from backend.database import get_session
from backend.config import settings
from backend.api.deps import get_current_user
from backend.models.user import User
from backend.models.outreach import OutreachMessage
from backend.models.lead import Lead
from backend.models.linkedin import LinkedInCredential, LinkedInPreference
from backend.services.integrations.linkedin import (
    LinkedInAPIClient, 
    LinkedInConfig, 
    LinkedInService,
    get_linkedin_service
)


router = APIRouter(prefix="/api/linkedin", tags=["linkedin"])


# =============================================================================
# SCHEMAS
# =============================================================================

class LinkedInConnectRequest(BaseModel):
    """Store LinkedIn credentials."""
    access_token: str
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    credential_type: str = "personal"  # personal or organization


class SetPreferenceRequest(BaseModel):
    """Set LinkedIn credential preference."""
    use_personal: bool = True  # True = personal, False = org's shared


class SendMessageRequest(BaseModel):
    """Send message via LinkedIn API."""
    lead_id: uuid.UUID
    message: str
    message_type: str = "inmail"  # inmail, connection


class LinkedInStatusResponse(BaseModel):
    """LinkedIn connection status."""
    personal_connected: bool = False
    personal_profile_name: Optional[str] = None
    org_connected: bool = False
    org_profile_name: Optional[str] = None
    org_connected_by: Optional[str] = None
    using_personal: bool = True
    has_sales_navigator: bool = False


class CredentialResponse(BaseModel):
    """LinkedIn credential info."""
    id: str
    credential_type: str
    profile_name: Optional[str]
    profile_url: Optional[str]
    has_sales_navigator: bool
    is_active: bool
    connected_at: str


class WebhookPayload(BaseModel):
    """LinkedIn webhook payload."""
    event_type: str
    resource_id: Optional[str] = None
    data: Optional[dict] = None


# =============================================================================
# CREDENTIAL HELPERS
# =============================================================================

async def get_user_credential(
    user_id: uuid.UUID, 
    session: AsyncSession
) -> Optional[LinkedInCredential]:
    """Get user's personal LinkedIn credential."""
    query = select(LinkedInCredential).where(
        LinkedInCredential.user_id == user_id,
        LinkedInCredential.credential_type == "personal",
        LinkedInCredential.is_active == True
    )
    result = await session.exec(query)
    return result.first()


async def get_org_credential(
    org_id: uuid.UUID, 
    session: AsyncSession
) -> Optional[LinkedInCredential]:
    """Get organization's shared LinkedIn credential."""
    query = select(LinkedInCredential).where(
        LinkedInCredential.org_id == org_id,
        LinkedInCredential.credential_type == "organization",
        LinkedInCredential.is_active == True
    )
    result = await session.exec(query)
    return result.first()


async def get_user_preference(
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    session: AsyncSession
) -> Optional[LinkedInPreference]:
    """Get user's preference for which credential to use in this org."""
    query = select(LinkedInPreference).where(
        LinkedInPreference.user_id == user_id,
        LinkedInPreference.org_id == org_id
    )
    result = await session.exec(query)
    return result.first()


async def get_active_token(
    user: User,
    session: AsyncSession
) -> tuple[Optional[str], str]:
    """
    Get the LinkedIn token to use based on user preference.
    Returns (token, source) where source is 'personal' or 'organization'.
    """
    # Get preference
    preference = await get_user_preference(user.id, user.current_org_id, session)
    use_personal = preference.use_personal if preference else True
    
    if use_personal:
        # Try personal credential
        cred = await get_user_credential(user.id, session)
        if cred:
            return cred.access_token, "personal"
    
    # Try org credential (fallback or preference)
    org_cred = await get_org_credential(user.current_org_id, session)
    if org_cred:
        return org_cred.access_token, "organization"
    
    # If preference was org but no org credential, try personal
    if not use_personal:
        cred = await get_user_credential(user.id, session)
        if cred:
            return cred.access_token, "personal"
    
    return None, "none"


# =============================================================================
# CREDENTIAL MANAGEMENT ENDPOINTS
# =============================================================================

@router.get("/credentials")
async def list_credentials(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    List all LinkedIn credentials available to user.
    Shows personal credential and org's shared credential.
    """
    personal = await get_user_credential(current_user.id, session)
    org = await get_org_credential(current_user.current_org_id, session)
    preference = await get_user_preference(
        current_user.id, 
        current_user.current_org_id, 
        session
    )
    
    credentials = []
    
    if personal:
        credentials.append({
            "id": str(personal.id),
            "type": "personal",
            "profile_name": personal.linkedin_profile_name,
            "profile_url": personal.linkedin_profile_url,
            "has_sales_navigator": personal.has_sales_navigator,
            "connected_at": personal.created_at.isoformat()
        })
    
    if org:
        # Get who connected it
        connected_by_name = None
        if org.connected_by_user_id:
            connected_by = await session.get(User, org.connected_by_user_id)
            connected_by_name = connected_by.full_name or connected_by.email if connected_by else None
        
        credentials.append({
            "id": str(org.id),
            "type": "organization",
            "profile_name": org.linkedin_profile_name,
            "profile_url": org.linkedin_profile_url,
            "has_sales_navigator": org.has_sales_navigator,
            "connected_by": connected_by_name,
            "connected_at": org.created_at.isoformat()
        })
    
    return {
        "credentials": credentials,
        "using_personal": preference.use_personal if preference else True,
        "has_personal": personal is not None,
        "has_organization": org is not None
    }


@router.get("/auth/url")
async def get_oauth_url(
    credential_type: str = Query(default="personal"),
    current_user: User = Depends(get_current_user)
):
    """
    Get LinkedIn OAuth authorization URL.
    
    Args:
        credential_type: 'personal' or 'organization'
    """
    config = LinkedInConfig(
        client_id=getattr(settings, 'LINKEDIN_CLIENT_ID', ''),
        client_secret=getattr(settings, 'LINKEDIN_CLIENT_SECRET', ''),
        redirect_uri=f"{getattr(settings, 'BACKEND_URL', 'http://localhost:8000')}/api/linkedin/callback"
    )
    
    if not config.client_id:
        raise HTTPException(
            status_code=400, 
            detail="LinkedIn integration not configured. Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET."
        )
    
    # Encode credential type in state: user_id:type:random
    state = f"{current_user.id}:{credential_type}:{secrets.token_urlsafe(16)}"
    
    client = LinkedInAPIClient()
    auth_url = client.get_auth_url(config, state)
    
    return {
        "auth_url": auth_url,
        "state": state,
        "credential_type": credential_type
    }


@router.get("/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    session: AsyncSession = Depends(get_session)
):
    """LinkedIn OAuth callback - stores credential in database."""
    # Parse state: user_id:type:random
    try:
        parts = state.split(":", 2)
        user_id = uuid.UUID(parts[0])
        credential_type = parts[1] if len(parts) > 1 else "personal"
    except:
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    
    # Get user
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=400, detail="User not found")
    
    # Exchange code for token
    config = LinkedInConfig(
        client_id=getattr(settings, 'LINKEDIN_CLIENT_ID', ''),
        client_secret=getattr(settings, 'LINKEDIN_CLIENT_SECRET', ''),
        redirect_uri=f"{getattr(settings, 'BACKEND_URL', 'http://localhost:8000')}/api/linkedin/callback"
    )
    
    client = LinkedInAPIClient()
    try:
        token_data = await client.exchange_code_for_token(code, config)
        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token')
        expires_in = token_data.get('expires_in', 5184000)  # Default 60 days
        
        # Get profile info
        client.access_token = access_token
        try:
            profile = await client.get_current_profile()
            profile_name = f"{profile.get('localizedFirstName', '')} {profile.get('localizedLastName', '')}".strip()
            profile_id = profile.get('id')
        except:
            profile_name = None
            profile_id = None
        
        # Deactivate any existing credential of same type
        if credential_type == "personal":
            query = select(LinkedInCredential).where(
                LinkedInCredential.user_id == user_id,
                LinkedInCredential.credential_type == "personal"
            )
        else:
            query = select(LinkedInCredential).where(
                LinkedInCredential.org_id == user.current_org_id,
                LinkedInCredential.credential_type == "organization"
            )
        
        result = await session.exec(query)
        for old_cred in result.all():
            old_cred.is_active = False
            session.add(old_cred)
        
        # Create new credential
        credential = LinkedInCredential(
            user_id=user_id if credential_type == "personal" else None,
            org_id=user.current_org_id if credential_type == "organization" else None,
            credential_type=credential_type,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=datetime.utcnow() + timedelta(seconds=expires_in) if expires_in else None,
            linkedin_profile_id=profile_id,
            linkedin_profile_name=profile_name,
            connected_by_user_id=user_id if credential_type == "organization" else None
        )
        session.add(credential)
        await session.commit()
        
        # Redirect to frontend
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        return RedirectResponse(
            url=f"{frontend_url}/settings/integrations?linkedin=connected&type={credential_type}"
        )
    except Exception as e:
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        return RedirectResponse(
            url=f"{frontend_url}/settings/integrations?linkedin=error&message={str(e)}"
        )
    finally:
        await client.close()


@router.post("/connect")
async def connect_linkedin(
    request: LinkedInConnectRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Manually connect LinkedIn with access token."""
    credential_type = request.credential_type
    
    # Deactivate existing
    if credential_type == "personal":
        query = select(LinkedInCredential).where(
            LinkedInCredential.user_id == current_user.id,
            LinkedInCredential.credential_type == "personal"
        )
    else:
        query = select(LinkedInCredential).where(
            LinkedInCredential.org_id == current_user.current_org_id,
            LinkedInCredential.credential_type == "organization"
        )
    
    result = await session.exec(query)
    for old_cred in result.all():
        old_cred.is_active = False
        session.add(old_cred)
    
    # Create new credential
    credential = LinkedInCredential(
        user_id=current_user.id if credential_type == "personal" else None,
        org_id=current_user.current_org_id if credential_type == "organization" else None,
        credential_type=credential_type,
        access_token=request.access_token,
        refresh_token=request.refresh_token,
        connected_by_user_id=current_user.id if credential_type == "organization" else None
    )
    session.add(credential)
    await session.commit()
    
    return {
        "message": f"LinkedIn {credential_type} credential connected successfully",
        "credential_type": credential_type
    }


@router.delete("/disconnect/{credential_type}")
async def disconnect_linkedin(
    credential_type: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Disconnect LinkedIn credential."""
    if credential_type == "personal":
        cred = await get_user_credential(current_user.id, session)
    else:
        cred = await get_org_credential(current_user.current_org_id, session)
    
    if cred:
        cred.is_active = False
        session.add(cred)
        await session.commit()
    
    return {"message": f"LinkedIn {credential_type} disconnected"}


@router.post("/preference")
async def set_preference(
    request: SetPreferenceRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Set which LinkedIn credential to use (personal or organization)."""
    preference = await get_user_preference(
        current_user.id, 
        current_user.current_org_id, 
        session
    )
    
    if preference:
        preference.use_personal = request.use_personal
        preference.updated_at = datetime.utcnow()
    else:
        preference = LinkedInPreference(
            user_id=current_user.id,
            org_id=current_user.current_org_id,
            use_personal=request.use_personal
        )
    
    session.add(preference)
    await session.commit()
    
    return {
        "message": f"Now using {'personal' if request.use_personal else 'organization'} LinkedIn",
        "use_personal": request.use_personal
    }


@router.get("/status")
async def get_linkedin_status(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get comprehensive LinkedIn status."""
    personal = await get_user_credential(current_user.id, session)
    org = await get_org_credential(current_user.current_org_id, session)
    preference = await get_user_preference(
        current_user.id, 
        current_user.current_org_id, 
        session
    )
    
    # Get org connected by name
    org_connected_by = None
    if org and org.connected_by_user_id:
        connected_by = await session.get(User, org.connected_by_user_id)
        org_connected_by = connected_by.full_name or connected_by.email if connected_by else None
    
    return LinkedInStatusResponse(
        personal_connected=personal is not None,
        personal_profile_name=personal.linkedin_profile_name if personal else None,
        org_connected=org is not None,
        org_profile_name=org.linkedin_profile_name if org else None,
        org_connected_by=org_connected_by,
        using_personal=preference.use_personal if preference else True,
        has_sales_navigator=bool((personal and personal.has_sales_navigator) or (org and org.has_sales_navigator))
    )


# =============================================================================
# MESSAGING ENDPOINTS
# =============================================================================

@router.post("/send")
async def send_linkedin_message(
    request: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Send a message via LinkedIn API using preferred credential."""
    # Get active token based on preference
    token, source = await get_active_token(current_user, session)
    
    if not token:
        raise HTTPException(
            status_code=400,
            detail="No LinkedIn account connected. Please connect your LinkedIn first."
        )
    
    # Get lead
    lead = await session.get(Lead, request.lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    if not lead.linkedin_url:
        raise HTTPException(status_code=400, detail="Lead has no LinkedIn URL")
    
    # Send message
    service = get_linkedin_service(token)
    try:
        result = await service.send_outreach_message(
            recipient_linkedin_url=lead.linkedin_url,
            message=request.message,
            message_type=request.message_type
        )
        
        # Record message
        outreach_msg = OutreachMessage(
            org_id=current_user.current_org_id,
            lead_id=lead.id,
            channel="linkedin",
            message=request.message,
            send_method="api",
            status="sent" if result.get("success") else "failed",
            linkedin_message_id=result.get("message_id"),
            linkedin_profile_url=lead.linkedin_url,
            sent_at=datetime.utcnow() if result.get("success") else None,
            error_message=result.get("error")
        )
        session.add(outreach_msg)
        await session.commit()
        
        return {
            "success": result.get("success", False),
            "sent_via": source,  # Shows which credential was used
            "message_id": str(outreach_msg.id),
            "linkedin_message_id": result.get("message_id"),
            "error": result.get("error")
        }
    finally:
        await service.close()


@router.post("/send-batch")
async def send_batch_messages(
    lead_ids: list[uuid.UUID],
    message_template: str,
    message_type: str = "inmail",
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Send to multiple leads using preferred credential."""
    token, source = await get_active_token(current_user, session)
    if not token:
        raise HTTPException(status_code=400, detail="No LinkedIn connected")
    
    results = []
    service = get_linkedin_service(token)
    
    try:
        for lead_id in lead_ids:
            lead = await session.get(Lead, lead_id)
            if not lead or not lead.linkedin_url:
                results.append({"lead_id": str(lead_id), "success": False, "error": "No LinkedIn URL"})
                continue
            
            # Personalize
            msg = message_template.replace("{{name}}", lead.name or "")
            msg = msg.replace("{{company}}", lead.company or "")
            msg = msg.replace("{{title}}", lead.title or "")
            msg = msg.replace("{{first_name}}", (lead.name or "").split()[0] if lead.name else "")
            
            result = await service.send_outreach_message(lead.linkedin_url, msg, message_type)
            
            outreach_msg = OutreachMessage(
                org_id=current_user.current_org_id,
                lead_id=lead.id,
                channel="linkedin",
                message=msg,
                send_method="api",
                status="sent" if result.get("success") else "failed",
                linkedin_message_id=result.get("message_id"),
                sent_at=datetime.utcnow() if result.get("success") else None
            )
            session.add(outreach_msg)
            results.append({"lead_id": str(lead_id), "success": result.get("success", False)})
        
        await session.commit()
    finally:
        await service.close()
    
    return {
        "sent_via": source,
        "total": len(lead_ids),
        "successful": sum(1 for r in results if r.get("success")),
        "results": results
    }


# =============================================================================
# WEBHOOK ENDPOINTS
# =============================================================================

@router.post("/webhook")
async def linkedin_webhook(
    payload: WebhookPayload,
    session: AsyncSession = Depends(get_session)
):
    """Handle LinkedIn webhooks."""
    event_type = payload.event_type
    resource_id = payload.resource_id
    
    if resource_id:
        query = select(OutreachMessage).where(
            OutreachMessage.linkedin_message_id == resource_id
        )
        result = await session.exec(query)
        message = result.first()
        
        if message:
            if event_type == "MESSAGE_DELIVERED":
                message.status = "delivered"
                message.delivered_at = datetime.utcnow()
            elif event_type == "MESSAGE_OPENED":
                message.status = "opened"
                message.opened_at = datetime.utcnow()
            elif event_type == "MESSAGE_REPLIED":
                message.status = "replied"
                message.replied_at = datetime.utcnow()
            
            session.add(message)
            await session.commit()
    
    return {"status": "received", "event_type": event_type}


@router.get("/webhook")
async def verify_webhook(challenge: str = Query(None)):
    """LinkedIn webhook verification."""
    if challenge:
        return {"challenge": challenge}
    return {"status": "ok"}
