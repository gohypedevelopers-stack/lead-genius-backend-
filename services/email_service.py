"""
Email service - handles sending emails.
Currently supports: Mock (development) and SMTP (production ready).
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from abc import ABC, abstractmethod

from backend.config import settings


class EmailService(ABC):
    """Base email service interface."""
    
    @abstractmethod
    async def send_email(
        self, 
        to: str, 
        subject: str, 
        body: str, 
        html: Optional[str] = None
    ) -> bool:
        """Send an email."""
        pass
    
    async def send_verification_email(self, to: str, token: str, base_url: str) -> bool:
        """Send email verification email."""
        verify_link = f"{base_url}/verify-email?token={token}"
        
        subject = "Verify your Lead Genius account"
        body = f"""
Hello,

Please verify your email by clicking the link below:

{verify_link}

This link expires in 24 hours.

If you didn't create an account, please ignore this email.

Best regards,
Lead Genius Team
        """
        
        html = f"""
        <html>
        <body>
            <h2>Welcome to Lead Genius!</h2>
            <p>Please verify your email by clicking the button below:</p>
            <p>
                <a href="{verify_link}" 
                   style="background-color: #4CAF50; color: white; padding: 14px 25px; 
                          text-decoration: none; display: inline-block; border-radius: 4px;">
                    Verify Email
                </a>
            </p>
            <p>Or copy this link: {verify_link}</p>
            <p><small>This link expires in 24 hours.</small></p>
        </body>
        </html>
        """
        
        return await self.send_email(to, subject, body, html)
    
    async def send_password_reset_email(self, to: str, token: str, base_url: str) -> bool:
        """Send password reset email."""
        reset_link = f"{base_url}/reset-password?token={token}"
        
        subject = "Reset your Lead Genius password"
        body = f"""
Hello,

You requested to reset your password. Click the link below:

{reset_link}

This link expires in 1 hour.

If you didn't request this, please ignore this email.

Best regards,
Lead Genius Team
        """
        
        html = f"""
        <html>
        <body>
            <h2>Password Reset Request</h2>
            <p>Click the button below to reset your password:</p>
            <p>
                <a href="{reset_link}" 
                   style="background-color: #2196F3; color: white; padding: 14px 25px; 
                          text-decoration: none; display: inline-block; border-radius: 4px;">
                    Reset Password
                </a>
            </p>
            <p>Or copy this link: {reset_link}</p>
            <p><small>This link expires in 1 hour.</small></p>
        </body>
        </html>
        """
        
        return await self.send_email(to, subject, body, html)


class MockEmailService(EmailService):
    """
    Mock email service for development.
    Prints emails to console instead of sending.
    """
    
    # Store sent emails for testing/debugging
    sent_emails: list = []
    
    async def send_email(
        self, 
        to: str, 
        subject: str, 
        body: str, 
        html: Optional[str] = None
    ) -> bool:
        """Mock send - prints to console and stores for debugging."""
        email_data = {
            "to": to,
            "subject": subject,
            "body": body
        }
        self.sent_emails.append(email_data)
        
        print("\n" + "=" * 60)
        print("📧 MOCK EMAIL (Development Mode)")
        print("=" * 60)
        print(f"To: {to}")
        print(f"Subject: {subject}")
        print("-" * 60)
        print(body)
        print("=" * 60 + "\n")
        
        return True
    
    def get_last_email(self) -> Optional[dict]:
        """Get the last sent email (for testing)."""
        return self.sent_emails[-1] if self.sent_emails else None


class SMTPEmailService(EmailService):
    """
    SMTP email service for production.
    Configure with environment variables:
    - SMTP_HOST
    - SMTP_PORT
    - SMTP_USER
    - SMTP_PASSWORD
    - EMAIL_FROM
    """
    
    def __init__(self):
        self.host = getattr(settings, 'SMTP_HOST', 'smtp.gmail.com')
        self.port = getattr(settings, 'SMTP_PORT', 587)
        self.user = getattr(settings, 'SMTP_USER', '')
        self.password = getattr(settings, 'SMTP_PASSWORD', '')
        self.from_email = getattr(settings, 'EMAIL_FROM', 'noreply@leadgenius.com')
    
    async def send_email(
        self, 
        to: str, 
        subject: str, 
        body: str, 
        html: Optional[str] = None
    ) -> bool:
        """Send email via SMTP."""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = to
            
            # Add plain text
            part1 = MIMEText(body, 'plain')
            msg.attach(part1)
            
            # Add HTML if provided
            if html:
                part2 = MIMEText(html, 'html')
                msg.attach(part2)
            
            # Send
            with smtplib.SMTP(self.host, self.port) as server:
                server.starttls()
                if self.user and self.password:
                    server.login(self.user, self.password)
                server.sendmail(self.from_email, to, msg.as_string())
            
            print(f"✅ Email sent to {to}: {subject}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send email to {to}: {e}")
            return False


# =============================================================================
# EMAIL SERVICE SINGLETON
# =============================================================================

_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Get the email service instance."""
    global _email_service
    
    if _email_service is None:
        # Check if we have SMTP configured
        smtp_host = getattr(settings, 'SMTP_HOST', None)
        
        if smtp_host:
            print("📧 Using SMTP Email Service")
            _email_service = SMTPEmailService()
        else:
            print("📧 Using Mock Email Service (emails printed to console)")
            _email_service = MockEmailService()
    
    return _email_service


def set_email_service(service: EmailService) -> None:
    """Set custom email service (for testing)."""
    global _email_service
    _email_service = service
