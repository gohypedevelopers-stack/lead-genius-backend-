"""
Email provider implementations.
Mock provider included, ready for real providers.
"""
import asyncio
from typing import Dict, Any, Optional

from backend.services.integrations.base import EmailProvider


class MockEmailProvider(EmailProvider):
    """
    Mock email provider for development/testing.
    Logs emails instead of sending them.
    """
    
    async def send(
        self, 
        to: str, 
        subject: str, 
        body: str,
        from_email: Optional[str] = None
    ) -> bool:
        """Mock email sending - logs instead of sending."""
        await asyncio.sleep(0.2)
        
        # Log the email (in production, this would send via SMTP/API)
        print(f"[MOCK EMAIL] To: {to}, Subject: {subject}")
        print(f"[MOCK EMAIL] Body: {body[:100]}...")
        
        return True
    
    async def send_template(
        self,
        to: str,
        template_id: str,
        variables: Dict[str, Any]
    ) -> bool:
        """Mock template email sending."""
        await asyncio.sleep(0.2)
        
        print(f"[MOCK EMAIL] To: {to}, Template: {template_id}")
        print(f"[MOCK EMAIL] Variables: {variables}")
        
        return True


# Future providers
"""
class SendGridEmailProvider(EmailProvider):
    '''SendGrid email provider.'''
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    async def send(self, to: str, subject: str, body: str, from_email: Optional[str] = None) -> bool:
        # Implement SendGrid API call
        pass
    
    async def send_template(self, to: str, template_id: str, variables: Dict[str, Any]) -> bool:
        # Implement SendGrid template sending
        pass


class SESEmailProvider(EmailProvider):
    '''AWS SES email provider.'''
    
    def __init__(self, region: str):
        self.region = region
    
    async def send(self, to: str, subject: str, body: str, from_email: Optional[str] = None) -> bool:
        # Implement AWS SES API call
        pass
    
    async def send_template(self, to: str, template_id: str, variables: Dict[str, Any]) -> bool:
        # Implement AWS SES template sending
        pass
"""


# Provider factory
_current_provider: EmailProvider = None


def get_email_provider() -> EmailProvider:
    """Get the current email provider instance."""
    global _current_provider
    if _current_provider is None:
        _current_provider = MockEmailProvider()
    return _current_provider


def set_email_provider(provider: EmailProvider) -> None:
    """Set the email provider."""
    global _current_provider
    _current_provider = provider
