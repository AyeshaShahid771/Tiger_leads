import logging
from datetime import datetime
from src.app.utils.email_resend import send_email_resend

logger = logging.getLogger(__name__)


def send_team_invitation_email_resend(
    recipient_email: str, inviter_name: str, invitation_token: str, frontend_url: str
):
    """Send team invitation email using Resend.
    
    Args:
        recipient_email: Email of the person being invited
        inviter_name: Name/email of the main account holder sending the invitation
        invitation_token: Unique token for the invitation (not used in URL)
        frontend_url: Base URL of the frontend application
    
    Returns (True, None) or (False, error_message).
    """
    subject = f"You're invited to join {inviter_name}'s team on Tigerleads.ai"
    year = datetime.utcnow().year
    login_link = f"{frontend_url}/login"
    
    html_content = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: 'Segoe UI', Roboto, Arial, sans-serif; background-color: #f9f9fb; color: #333; margin: 0; padding: 0;">
            <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); overflow: hidden;">
                <!-- Header -->
                <div style="background-color: #ffffff; text-align: center; padding: 25px 0; border-bottom: 1px solid #eee;">
                    <h1 style="color: #f58220; margin: 0;">Tiger Leads</h1>
                </div>

                <div style="padding: 30px;">
                    <h2 style="color: #222; margin-top: 0;">You're Invited to Join a Team!</h2>
                    <p style="line-height: 1.6; font-size: 16px;">
                        Hi there,
                    </p>
                    <p style="line-height: 1.6; font-size: 16px;">
                        <strong style="color: #f58220;">{inviter_name}</strong> has invited you to join their team on <strong>Tigerleads.ai</strong>
                    </p>

                    <div style="background-color: #fff3e0; border-left: 4px solid #f58220; padding: 20px; margin: 25px 0; border-radius: 6px;">
                        <p style="margin: 0 0 12px 0; font-size: 15px; color: #e65100; font-weight: 600;">📧 To Accept This Invitation:</p>
                        <p style="margin: 0; font-size: 14px; color: #333; line-height: 1.8;">
                            <strong>Login with this email:</strong> <span style="color: #f58220; font-weight: 600;">{recipient_email}</span><br>
                            <strong>Enter your password</strong> (or create one if you don't have an account yet)<br>
                            <strong>You will be redirected to {inviter_name}'s dashboard</strong>
                        </p>
                    </div>

                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{login_link}" style="background-color: #f58220; color: #fff; text-decoration: none; padding: 16px 40px; border-radius: 6px; font-weight: 600; display: inline-block; font-size: 16px; box-shadow: 0 2px 8px rgba(245, 130, 32, 0.3);">
                            Login to Accept Invitation
                        </a>
                    </div>

                    <div style="background-color: #e8f5e9; border-radius: 6px; padding: 20px; margin: 25px 0;">
                        <p style="margin: 0 0 12px 0; font-weight: 600; color: #2e7d32; font-size: 15px;">✨ What Happens Next:</p>
                        <ul style="margin: 0; padding-left: 20px; line-height: 2;">
                            <li style="margin-bottom: 8px;">Click the button above to go to the login page</li>
                            <li style="margin-bottom: 8px;">If you already have an account: Login with <strong>{recipient_email}</strong> and your password</li>
                            <li style="margin-bottom: 8px;">If you don't have an account: Click "Sign Up" and create one using <strong>{recipient_email}</strong></li>
                            <li style="margin-bottom: 8px;">After logging in, you'll automatically be redirected to <strong>{inviter_name}'s dashboard</strong></li>
                            <li style="margin-bottom: 0;">You'll have access to shared leads and team resources</li>
                        </ul>
                    </div>

                    <div style="background-color: #fff3e0; border-radius: 6px; padding: 15px; margin: 20px 0;">
                        <p style="margin: 0; font-size: 14px; color: #e65100; line-height: 1.6;">
                            <strong>⚠️ Important:</strong> You must use the email address <strong>{recipient_email}</strong> to accept this invitation. This email will be linked to {inviter_name}'s account.
                        </p>
                    </div>

                    <p style="line-height: 1.6; color: #666; font-size: 14px;">
                        <strong>Good news:</strong> This invitation never expires. You can accept it whenever you're ready!
                    </p>

                    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

                    <p style="font-size: 14px; color: #777; margin-bottom: 8px;">
                        If the button doesn't work, copy and paste this link into your browser:
                    </p>
                    <p style="word-break: break-all; font-size: 13px; background-color: #f8f9fa; padding: 10px; border-radius: 4px;">
                        <a href="{login_link}" style="color: #f58220; text-decoration: none;">{login_link}</a>
                    </p>

                    <p style="margin-top: 30px; line-height: 1.6; color: #666;">
                        Questions? Reply to this email or contact our support team.
                    </p>

                    <p style="margin-top: 25px;">Best regards,<br><strong style="color: #f58220;">The Tigerleads.ai Team</strong></p>
                </div>

                <div style="background-color: #fafafa; text-align: center; padding: 20px; font-size: 12px; color: #777; border-top: 1px solid #eee;">
                    &copy; {year} Tiger Leads.ai. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """
    
    try:
        result = send_email_resend(recipient_email, subject, html_content)
        logger.info(f"Team invitation email sent successfully to {recipient_email} via Resend")
        return True, None
    except Exception as e:
        logger.error(f"Failed to send team invitation email via Resend to {recipient_email}: {str(e)}")
        return False, f"Failed to send invitation email: {str(e)}"
