"""
LinkedIn API integration service.
Handles OAuth, sending InMails, and tracking.

Note: Requires LinkedIn Developer Account and Sales Navigator subscription.
"""
import uuid
import httpx
from datetime import datetime
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
from pydantic import BaseModel

from backend.config import settings


# =============================================================================
# CONFIGURATION
# =============================================================================

class LinkedInConfig(BaseModel):
    """LinkedIn API configuration."""
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = "http://localhost:8000/api/linkedin/callback"
    scopes: list = ["r_liteprofile", "w_member_social"]
    
    # Sales Navigator specific
    has_sales_navigator: bool = False


# =============================================================================
# LINKEDIN API CLIENT
# =============================================================================

class LinkedInAPIClient:
    """
    LinkedIn API client for sending messages.
    
    Note: Full messaging API requires Sales Navigator.
    Without it, we can only:
    - Read profile data
    - Post to feed (with permission)
    
    With Sales Navigator:
    - Send InMails
    - Message connections
    """
    
    BASE_URL = "https://api.linkedin.com/v2"
    AUTH_URL = "https://www.linkedin.com/oauth/v2"
    
    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token
        self.client = httpx.AsyncClient()
    
    @property
    def headers(self) -> Dict[str, str]:
        """Get authorization headers."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }
    
    # -------------------------------------------------------------------------
    # OAuth Flow
    # -------------------------------------------------------------------------
    
    def get_auth_url(self, config: LinkedInConfig, state: str) -> str:
        """
        Generate OAuth authorization URL.
        User visits this to authorize the app.
        """
        scopes = "%20".join(config.scopes)
        return (
            f"{self.AUTH_URL}/authorization?"
            f"response_type=code&"
            f"client_id={config.client_id}&"
            f"redirect_uri={config.redirect_uri}&"
            f"scope={scopes}&"
            f"state={state}"
        )
    
    async def exchange_code_for_token(
        self, 
        code: str, 
        config: LinkedInConfig
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        Called after OAuth callback.
        """
        response = await self.client.post(
            f"{self.AUTH_URL}/accessToken",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": config.redirect_uri,
                "client_id": config.client_id,
                "client_secret": config.client_secret
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Token exchange failed: {response.text}")
    
    # -------------------------------------------------------------------------
    # Profile Operations
    # -------------------------------------------------------------------------
    
    async def get_current_profile(self) -> Dict[str, Any]:
        """Get the authenticated user's profile."""
        response = await self.client.get(
            f"{self.BASE_URL}/me",
            headers=self.headers
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get profile: {response.text}")
    
    async def get_profile_by_id(self, profile_id: str) -> Dict[str, Any]:
        """Get a profile by LinkedIn ID."""
        response = await self.client.get(
            f"{self.BASE_URL}/people/{profile_id}",
            headers=self.headers
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get profile: {response.text}")
    
    # -------------------------------------------------------------------------
    # Messaging (Requires Sales Navigator)
    # -------------------------------------------------------------------------
    
    async def send_inmail(
        self,
        recipient_id: str,
        subject: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Send an InMail message.
        
        Note: Requires Sales Navigator and messaging permissions.
        
        Args:
            recipient_id: LinkedIn member URN (urn:li:person:xxx)
            subject: InMail subject
            message: InMail body
        
        Returns:
            Response from LinkedIn API
        """
        payload = {
            "recipients": [recipient_id],
            "subject": subject,
            "body": message
        }
        
        # Note: This is a simplified example
        # Actual Sales Navigator API may differ
        response = await self.client.post(
            f"{self.BASE_URL}/messages",
            json=payload,
            headers=self.headers
        )
        
        if response.status_code in [200, 201]:
            return {
                "success": True,
                "message_id": response.json().get("id"),
                "status": "sent"
            }
        else:
            return {
                "success": False,
                "error": response.text,
                "status": "failed"
            }
    
    async def send_connection_request(
        self,
        profile_id: str,
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a connection request.
        
        Args:
            profile_id: LinkedIn profile ID
            message: Optional connection note (max 300 chars)
        """
        payload = {
            "invitations": [{
                "invitee": {
                    "com.linkedin.voyager.growth.invitation.InviteeProfile": {
                        "profileId": profile_id
                    }
                },
                "message": message[:300] if message else None
            }]
        }
        
        response = await self.client.post(
            f"{self.BASE_URL}/invitations",
            json=payload,
            headers=self.headers
        )
        
        return {
            "success": response.status_code in [200, 201],
            "status_code": response.status_code
        }
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# =============================================================================
# SERVICE LAYER
# =============================================================================

class LinkedInService:
    """
    High-level service for LinkedIn operations.
    Wraps the API client with business logic.
    """
    
    def __init__(self, access_token: Optional[str] = None):
        self.client = LinkedInAPIClient(access_token)
    
    async def send_outreach_message(
        self,
        recipient_linkedin_url: str,
        message: str,
        message_type: str = "inmail"
    ) -> Dict[str, Any]:
        """
        Send an outreach message via LinkedIn.
        
        Args:
            recipient_linkedin_url: LinkedIn profile URL
            message: Message content
            message_type: 'inmail' or 'connection'
        
        Returns:
            Result with success status and message ID
        """
        # Extract profile ID from URL
        # URL format: https://www.linkedin.com/in/username/
        profile_id = self._extract_profile_id(recipient_linkedin_url)
        
        if not profile_id:
            return {
                "success": False,
                "error": "Invalid LinkedIn URL"
            }
        
        if message_type == "connection":
            return await self.client.send_connection_request(profile_id, message)
        else:
            return await self.client.send_inmail(
                recipient_id=f"urn:li:person:{profile_id}",
                subject="",  # InMail subject
                message=message
            )
    
    def _extract_profile_id(self, linkedin_url: str) -> Optional[str]:
        """Extract profile ID from LinkedIn URL."""
        if not linkedin_url:
            return None
        
        # Handle different URL formats
        # https://www.linkedin.com/in/username/
        # https://linkedin.com/in/username
        if "/in/" in linkedin_url:
            parts = linkedin_url.split("/in/")
            if len(parts) > 1:
                return parts[1].strip("/").split("?")[0]
        
        return None
    
    async def close(self):
        """Cleanup resources."""
        await self.client.close()


# =============================================================================
# MOCK SERVICE (For Development)
# =============================================================================

class MockLinkedInService(LinkedInService):
    """
    Mock LinkedIn service for development/testing.
    Simulates API responses without actual LinkedIn calls.
    """
    
    async def send_outreach_message(
        self,
        recipient_linkedin_url: str,
        message: str,
        message_type: str = "inmail"
    ) -> Dict[str, Any]:
        """Mock sending a message."""
        print(f"\n📧 MOCK LinkedIn Message")
        print(f"To: {recipient_linkedin_url}")
        print(f"Type: {message_type}")
        print(f"Message: {message[:100]}...")
        
        # Simulate success
        return {
            "success": True,
            "message_id": f"mock-msg-{uuid.uuid4().hex[:8]}",
            "status": "sent",
            "mock": True
        }


# =============================================================================
# FACTORY
# =============================================================================

def get_linkedin_service(access_token: Optional[str] = None) -> LinkedInService:
    """
    Get the appropriate LinkedIn service.
    Returns mock in development, real in production.
    """
    if getattr(settings, 'DEV_MODE', True):
        return MockLinkedInService(access_token)
    else:
        return LinkedInService(access_token)
