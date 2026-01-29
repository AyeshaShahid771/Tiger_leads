"""
2FA Recovery Email Template

This module contains the email template for 2FA recovery codes.
"""

import base64
import logging
from datetime import datetime
from pathlib import Path

from src.app.utils.email_resend import send_email_resend

logger = logging.getLogger(__name__)
LOGO_PATH = Path("app/static/logo.png")


def is_valid_email(email: str) -> tuple[bool, str | None]:
    """Validate email format. Returns (is_valid, error_message)."""
    import re
    if not email or not isinstance(email, str):
        return False, "Email must be a non-empty string"
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email.strip()):
        return False, "Invalid email format"
    return True, None


async def send_2fa_recovery_email(recipient_email: str, code: str):
    """Send 2FA recovery code to user's email.
    
    This allows users who lost access to their authenticator app to
    bypass 2FA temporarily using an email OTP.
    
    Returns (True, None) on success or (False, error_message) on failure.
    """
    # Validate email
    is_valid, result = is_valid_email(recipient_email)
    if not is_valid:
        logger.error(f"Invalid email format: {recipient_email}")
        return False, "Please provide a valid email address format"

    subject = "2FA Recovery Code – Tiger Leads.ai"
    year = datetime.utcnow().year

    # Try to load logo as base64
    logo_base64 = None
    if LOGO_PATH.exists():
        try:
            with open(LOGO_PATH, "rb") as img_file:
                logo_base64 = base64.b64encode(img_file.read()).decode("utf-8")
        except Exception:
            logo_base64 = None

    logo_html = (
        f'<img src="data:image/png;base64,{logo_base64}" alt="Tiger Leads" style="width: 160px; height: auto;" />'
        if logo_base64
        else '<h1 style="color: #f58220; margin: 0;">Tiger Leads</h1>'
    )

    html_content = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: 'Segoe UI', Roboto, Arial, sans-serif; background-color: #f9f9fb; color: #333; margin: 0; padding: 0;">
            <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); overflow: hidden;">
                <!-- Header with embedded Logo -->
                <div style="background-color: #ffffff; text-align: center; padding: 25px 0; border-bottom: 1px solid #eee;">
                    {logo_html}
                </div>

                <div style="padding: 30px;">
                    <h2 style="color: #222;">🔐 2FA Recovery Request</h2>
                    <p style="line-height: 1.6;">
                        We received a request to recover your Two-Factor Authentication (2FA) access. 
                        Use the code below to bypass 2FA and login to your account:
                    </p>

                    <div style="text-align: center; margin: 30px 0;">
                        <div style="background-color: #fff3e0; border: 2px dashed #ff9800; border-radius: 8px; padding: 20px; display: inline-block;">
                            <p style="margin: 0; font-size: 14px; color: #666; font-weight: 500;">Your Recovery Code</p>
                            <p style="margin: 10px 0 0 0; font-size: 32px; font-weight: bold; color: #ff9800; letter-spacing: 4px; font-family: 'Courier New', monospace;">{code}</p>
                        </div>
                    </div>

                    <p style="color: #d35400; font-weight: bold; text-align: center;">⏱️ This code will expire in 10 minutes</p>

                    <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 4px;">
                        <p style="margin: 0; color: #856404; font-weight: bold;">⚠️ Security Notice</p>
                        <p style="margin: 10px 0 0 0; color: #856404; font-size: 14px;">
                            If you didn't request this code, please ignore this email and ensure your account is secure.
                            Consider changing your password if you suspect unauthorized access.
                        </p>
                    </div>

                    <p style="margin-top: 30px; line-height: 1.6;">
                        After logging in, we recommend setting up 2FA again or ensuring you have access to your authenticator app.
                    </p>

                    <p style="margin-top: 30px;">Best regards,<br><strong>The Tiger Leads.ai Team</strong></p>
                </div>

                <div style="background-color: #fafafa; text-align: center; padding: 15px; font-size: 12px; color: #777; border-top: 1px solid #eee;">
                    &copy; {year} Tiger Leads. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """

    try:
        send_email_resend(recipient_email, subject, html_content)
        logger.info(f"2FA recovery email sent successfully to {recipient_email} via Resend")
        return True, None
    except Exception as e:
        logger.error(f"Failed to send 2FA recovery email to {recipient_email}: {str(e)}")
        return False, "Failed to send 2FA recovery email"
