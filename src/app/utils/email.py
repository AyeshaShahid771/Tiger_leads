import base64
import logging
import os
import re
from datetime import datetime
from pathlib import Path

# Import Resend helper
from src.app.utils.email_resend import send_email_resend

# Configure logger
logger = logging.getLogger(__name__)

# Logo path
LOGO_PATH = Path("app/static/logo.png")

# Frontend base URL — used in email CTAs
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://app.tigerleads.ai")


# Email validation helper
def is_valid_email(email: str) -> tuple[bool, str | None]:  # type: ignore
    """Validate email format. Returns (is_valid, error_message)."""
    if not email or not isinstance(email, str):
        return False, "Email must be a non-empty string"
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_pattern, email.strip()):
        return False, "Invalid email format"
    return True, None


async def send_admin_invitation_email(
    recipient_email: str, inviter_name: str, role: str, signup_url: str, token: str
):
    """Send an admin invitation email containing a signup link and token.

    Returns (True, None) on success or (False, error_message) on failure.
    """
    # Validate email
    is_valid, result = is_valid_email(recipient_email)
    if not is_valid:
        logger.error(f"Invalid email format: {recipient_email}")
        return False, "Please provide a valid email address format"

    subject = f"Admin Invitation to Tiger Leads.ai — Role: {role}"
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
        f'<img src="data:image/png;base64,{logo_base64}" alt="Tiger Leads" style="width:160px;height:auto;" />'
        if logo_base64
        else '<h1 style="color:#f58220; margin:0;">Tiger Leads</h1>'
    )

    signup_link = f"{signup_url}?token={token}"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Admin Invitation</title></head>
<body style="margin:0;padding:0;background-color:#f4f4f7;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f7;padding:40px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:10px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);">

        <!-- Header -->
        <tr>
          <td style="background:#1a1a2e;padding:32px 40px;text-align:center;">
            {logo_html}
          </td>
        </tr>

        <!-- Orange accent bar -->
        <tr><td style="background:#f58220;height:4px;"></td></tr>

        <!-- Body -->
        <tr>
          <td style="padding:40px 40px 32px;">
            <h2 style="margin:0 0 8px;font-size:22px;color:#1a1a2e;">You've been invited to Tiger Leads.ai</h2>
            <p style="margin:0 0 24px;font-size:15px;color:#555;">
              <strong style="color:#1a1a2e;">{inviter_name}</strong> has invited you to join the admin team.
            </p>

            <!-- Role badge -->
            <table cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
              <tr>
                <td style="background:#fff4e8;border:1px solid #f58220;border-radius:6px;padding:10px 18px;">
                  <span style="font-size:12px;color:#999;text-transform:uppercase;letter-spacing:1px;">Assigned Role</span><br>
                  <span style="font-size:18px;font-weight:bold;color:#f58220;text-transform:capitalize;">{role}</span>
                </td>
              </tr>
            </table>

            <p style="margin:0 0 24px;font-size:14px;color:#555;">
              Click the button below to accept your invitation and complete your admin account setup.
              This link expires in <strong>7 days</strong>.
            </p>

            <!-- CTA Button -->
            <table cellpadding="0" cellspacing="0" style="margin-bottom:32px;">
              <tr>
                <td style="background:#f58220;border-radius:7px;">
                  <a href="{signup_link}" style="display:inline-block;padding:14px 32px;font-size:15px;font-weight:bold;color:#ffffff;text-decoration:none;letter-spacing:0.3px;">
                    Accept Invitation &rarr;
                  </a>
                </td>
              </tr>
            </table>

            <!-- Fallback URL -->
            <p style="margin:0 0 6px;font-size:13px;color:#888;">If the button doesn't work, copy and paste this link into your browser:</p>
            <p style="margin:0 0 24px;word-break:break-all;background:#f8f9fa;border-left:3px solid #f58220;padding:10px 14px;border-radius:4px;font-size:13px;color:#f58220;">{signup_link}</p>

            <!-- Token box -->
            <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8f9fa;border-radius:6px;margin-bottom:8px;">
              <tr>
                <td style="padding:14px 18px;">
                  <span style="font-size:12px;color:#999;text-transform:uppercase;letter-spacing:1px;">Your Signup Token</span><br>
                  <span style="font-size:20px;font-weight:bold;color:#1a1a2e;letter-spacing:3px;">{token}</span>
                </td>
              </tr>
            </table>
            <p style="margin:0 0 0;font-size:12px;color:#aaa;">Use this token on the signup page if prompted.</p>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#f8f9fa;border-top:1px solid #eee;padding:20px 40px;text-align:center;">
            <p style="margin:0 0 4px;font-size:13px;color:#888;">Thanks,<br><strong style="color:#1a1a2e;">The Tiger Leads.ai Team</strong></p>
            <p style="margin:8px 0 0;font-size:11px;color:#bbb;">&copy; {year} Tiger Leads.ai &mdash; All rights reserved</p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    try:
        send_email_resend(recipient_email, subject, html_content)
        logger.info(
            f"Admin invitation email sent successfully to {recipient_email} via Resend"
        )
        return True, None
    except Exception as e:
        logger.exception(
            "Failed to send admin invitation to %s: %s", recipient_email, e
        )
        return False, "Failed to send invitation email"


async def send_verification_email(recipient_email: str, code: str):
    """Send email verification code to user.

    Returns (True, None) on success or (False, error_message) on failure.
    """
    # Validate email
    is_valid, result = is_valid_email(recipient_email)
    if not is_valid:
        logger.error(f"Invalid email format: {recipient_email}")
        return False, "Please provide a valid email address format"

    subject = "Verify Your Email – Tiger Leads.ai"
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
                    <h2 style="color: #222;">Welcome to Tiger Leads.ai!</h2>
                    <p style="line-height: 1.6;">
                        Thank you for signing up. To complete your registration and verify your email address, please use the verification code below:
                    </p>

                    <div style="text-align: center; margin: 30px 0;">
                        <div style="background-color: #f8f9fa; border: 2px dashed #f58220; border-radius: 8px; padding: 20px; display: inline-block;">
                            <p style="margin: 0; font-size: 14px; color: #666; font-weight: 500;">Your Verification Code</p>
                            <p style="margin: 10px 0 0 0; font-size: 32px; font-weight: bold; color: #f58220; letter-spacing: 4px; font-family: 'Courier New', monospace;">{code}</p>
                        </div>
                    </div>

                    <p style="color: #d35400; font-weight: bold; text-align: center;">⏱️ This code will expire in 10 minutes</p>

                    <p style="margin-top: 30px; line-height: 1.6;">
                        Enter this code on the verification page to activate your account and start using Tiger Leads.ai.
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
        logger.info(
            f"Verification email sent successfully to {recipient_email} via Resend"
        )
        return True, None
    except Exception as e:
        logger.error(
            f"Failed to send verification email to {recipient_email}: {str(e)}"
        )
        return False, "Failed to send verification email"


async def send_team_invitation_email(
    recipient_email: str, inviter_name: str, invitation_token: str, frontend_url: str
):
    """Send team invitation email to a new team member.

    Args:
        recipient_email: Email of the person being invited
        inviter_name: Name/email of the main account holder sending the invitation
        invitation_token: Unique token for the invitation (not used in URL)
        frontend_url: Base URL of the frontend application

    Returns (True, None) or (False, error_message).
    """
    # Validate email
    is_valid, result = is_valid_email(recipient_email)
    if not is_valid:
        logger.error(f"Invalid email format: {recipient_email}")
        return False, "Please provide a valid email address format"

    subject = f"You're invited to join {inviter_name}'s team on Tigerleads.ai"
    year = datetime.utcnow().year
    login_link = f"{frontend_url}/login"

    # Try to load logo as base64
    logo_base64 = None
    if LOGO_PATH.exists():
        try:
            with open(LOGO_PATH, "rb") as img_file:
                logo_base64 = base64.b64encode(img_file.read()).decode("utf-8")
        except Exception:
            pass

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
        send_email_resend(recipient_email, subject, html_content)
        logger.info(
            f"Team invitation email sent successfully to {recipient_email} via Resend"
        )
        return True, None
    except Exception as e:
        logger.error(
            f"Failed to send team invitation email to {recipient_email}: {str(e)}"
        )
        return False, "Failed to send invitation email"


async def send_password_reset_email(recipient_email: str, reset_link: str):
    """Send password reset email with inline (CID) logo image using Resend.

    Uses `app/static/logo.png` as the embedded image. Returns (True, None) or (False, error).
    """
    # Validate email
    is_valid, result = is_valid_email(recipient_email)
    if not is_valid:
        logger.error(f"Invalid email format: {recipient_email}")
        return False, "Please provide a valid email address format"

    subject = "Reset Your Password – Tiger Leads.ai"
    year = datetime.utcnow().year

    # Try to load logo as base64 for Vercel compatibility
    logo_base64 = None
    if LOGO_PATH.exists():
        try:
            with open(LOGO_PATH, "rb") as img_file:
                logo_base64 = base64.b64encode(img_file.read()).decode("utf-8")
        except Exception:
            pass

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
                    <h2 style="color: #222;">Password Reset Request</h2>
                    <p style="line-height: 1.6;">
                        Hello,<br><br>
                        We received a request to reset your password for your <strong>Tiger Leads.ai</strong> account.
                        If you made this request, click the button below to set a new password.
                    </p>

                    <p style="color: #d35400; font-weight: bold;">This link will expire in 20 minutes.</p>

                    <div style="text-align: center; margin: 25px 0;">
                        <a href="{reset_link}" style="background-color: #f58220; color: #fff; text-decoration: none; padding: 12px 24px; border-radius: 6px; font-weight: 600; display: inline-block;">
                            Reset Password
                        </a>
                    </div>

                    <p style="font-size: 14px; color: #555;">
                        If the button doesn't work, copy and paste this link into your browser:
                    </p>
                    <p style="word-break: break-all;">
                        <a href="{reset_link}" style="color: #f58220;">{reset_link}</a>
                    </p>

                    <p style="margin-top: 30px;">
                        If you didn't request a password reset, you can safely ignore this email.
                    </p>

                    <p>Best regards,<br><strong>The Tiger Leads.ai Team</strong></p>
                </div>

                <div style="background-color: #fafafa; text-align: center; padding: 15px; font-size: 12px; color: #777; border-top: 1px solid #eee;">
                    &copy; {year} Tiger Leads.ai. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """

    try:
        send_email_resend(recipient_email, subject, html_content)
        logger.info(
            f"Password reset email sent successfully to {recipient_email} via Resend"
        )
        return True, None
    except Exception as e:
        logger.error(
            f"Failed to send password reset email to {recipient_email}: {str(e)}"
        )
        return False, "Failed to send password reset email"


async def send_registration_completion_email(
    recipient_email: str, user_name: str, role: str, login_url: str
):
    """Send registration completion email when contractor/supplier completes step 4.

    Args:
        recipient_email: Email of the user who completed registration
        user_name: Name of the user (company name or contact name)
        role: "Contractor" or "Supplier"
        login_url: URL to the login page

    Returns (True, None) on success or (False, error_message) on failure.
    """
    # Validate email
    is_valid, result = is_valid_email(recipient_email)
    if not is_valid:
        logger.error(f"Invalid email format: {recipient_email}")
        return False, "Please provide a valid email address format"

    subject = f"Registration Complete – Welcome to Tiger Leads.ai!"
    year = datetime.utcnow().year

    # Try to load logo as base64
    logo_base64 = None
    if LOGO_PATH.exists():
        try:
            with open(LOGO_PATH, "rb") as img_file:
                logo_base64 = base64.b64encode(img_file.read()).decode("utf-8")
        except Exception:
            pass

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
                    <h2 style="color: #222; margin-top: 0;">🎉 Thank You for Registering!</h2>
                    
                    <p style="line-height: 1.6; font-size: 16px;">
                        Hi <strong style="color: #f58220;">{user_name}</strong>,
                    </p>

                    <p style="line-height: 1.6; font-size: 16px;">
                        Thank you for completing your <strong>{role}</strong> registration on <strong>Tiger Leads.ai</strong>! 
                        We're excited to have you join our platform.
                    </p>

                    <div style="background-color: #fff3e0; border-left: 4px solid #f58220; padding: 20px; margin: 25px 0; border-radius: 6px;">
                        <p style="margin: 0 0 12px 0; font-size: 15px; color: #e65100; font-weight: 600;">📋 What's Next?</p>
                        <p style="margin: 0; font-size: 14px; color: #333; line-height: 1.8;">
                            Your account is currently <strong style="color: #f58220;">pending approval</strong> from our team. 
                            We review all new registrations to ensure the quality and security of our platform.
                        </p>
                    </div>

                    <div style="background-color: #e8f5e9; border-radius: 6px; padding: 20px; margin: 25px 0;">
                        <p style="margin: 0 0 12px 0; font-weight: 600; color: #2e7d32; font-size: 15px;">✨ Once Approved, You'll Be Able To:</p>
                        <ul style="margin: 0; padding-left: 20px; line-height: 2;">
                            <li style="margin-bottom: 8px;">Access exclusive leads tailored to your business</li>
                            <li style="margin-bottom: 8px;">Connect with potential clients in your service area</li>
                            <li style="margin-bottom: 8px;">Manage your profile and preferences</li>
                            <li style="margin-bottom: 0;">Grow your business with Tiger Leads.ai</li>
                        </ul>
                    </div>

                    <p style="line-height: 1.6; font-size: 16px;">
                        We'll notify you via email as soon as your account is approved. This typically takes <strong>1-2 business days</strong>.
                    </p>

                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{login_url}" style="background-color: #f58220; color: #fff; text-decoration: none; padding: 16px 40px; border-radius: 6px; font-weight: 600; display: inline-block; font-size: 16px; box-shadow: 0 2px 8px rgba(245, 130, 32, 0.3);">
                            Go to Login
                        </a>
                    </div>

                    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

                    <p style="font-size: 14px; color: #777; margin-bottom: 8px;">
                        If the button doesn't work, copy and paste this link into your browser:
                    </p>
                    <p style="word-break: break-all; font-size: 13px; background-color: #f8f9fa; padding: 10px; border-radius: 4px;">
                        <a href="{login_url}" style="color: #f58220; text-decoration: none;">{login_url}</a>
                    </p>

                    <p style="margin-top: 30px; line-height: 1.6; color: #666;">
                        Questions? Feel free to reply to this email or contact our support team.
                    </p>

                    <p style="margin-top: 25px;">Best regards,<br><strong style="color: #f58220;">The Tiger Leads.ai Team</strong></p>
                </div>

                <div style="background-color: #fafafa; text-align: center; padding: 20px; font-size: 12px; color: #777; border-top: 1px solid #eee;">
                    &copy; {year} Tiger Leads.ai. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """

    try:
        send_email_resend(recipient_email, subject, html_content)
        logger.info(
            f"Registration completion email sent successfully to {recipient_email} for {role} via Resend"
        )
        return True, None
    except Exception as e:
        logger.error(
            f"Failed to send registration completion email to {recipient_email}: {str(e)}"
        )
        return False, "Failed to send registration completion email"


async def send_admin_new_registration_notification(
    admin_email: str,
    user_name: str,
    user_email: str,
    role: str,
    company_name: str,
    registration_date: str,
    dashboard_url: str,
):
    """Send notification email to admin when a new user completes registration.

    Args:
        admin_email: Email of the admin to notify
        user_name: Name of the user (primary contact name)
        user_email: Email of the user who registered
        role: "Contractor" or "Supplier"
        company_name: Company name from registration
        registration_date: Formatted registration timestamp
        dashboard_url: URL to admin dashboard for review

    Returns (True, None) on success or (False, error_message) on failure.
    """
    # Validate email
    is_valid, result = is_valid_email(admin_email)
    if not is_valid:
        logger.error(f"Invalid admin email format: {admin_email}")
        return False, "Please provide a valid email address format"

    subject = f"🎉 New {role} Registration – {company_name}"
    year = datetime.utcnow().year

    # Try to load logo as base64
    logo_base64 = None
    if LOGO_PATH.exists():
        try:
            with open(LOGO_PATH, "rb") as img_file:
                logo_base64 = base64.b64encode(img_file.read()).decode("utf-8")
        except Exception:
            pass

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
                    <h2 style="color: #222; margin-top: 0;">🎉 New {role} Registration</h2>
                    
                    <p style="line-height: 1.6; font-size: 16px;">
                        A new <strong style="color: #f58220;">{role}</strong> has completed registration on Tiger Leads.ai and is awaiting approval.
                    </p>

                    <div style="background-color: #f8f9fa; border-radius: 8px; padding: 20px; margin: 25px 0;">
                        <p style="margin: 0 0 15px 0; font-weight: 600; color: #222; font-size: 15px;">📋 Registration Details:</p>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 8px 0; color: #666; font-size: 14px; width: 40%;">Company Name:</td>
                                <td style="padding: 8px 0; color: #222; font-weight: 600; font-size: 14px;">{company_name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #666; font-size: 14px;">Contact Name:</td>
                                <td style="padding: 8px 0; color: #222; font-weight: 600; font-size: 14px;">{user_name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #666; font-size: 14px;">Email:</td>
                                <td style="padding: 8px 0; color: #222; font-weight: 600; font-size: 14px;">{user_email}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #666; font-size: 14px;">Role:</td>
                                <td style="padding: 8px 0; color: #f58220; font-weight: 600; font-size: 14px;">{role}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #666; font-size: 14px;">Registration Date:</td>
                                <td style="padding: 8px 0; color: #222; font-weight: 600; font-size: 14px;">{registration_date}</td>
                            </tr>
                        </table>
                    </div>

                    <div style="background-color: #fff3e0; border-left: 4px solid #f58220; padding: 20px; margin: 25px 0; border-radius: 6px;">
                        <p style="margin: 0 0 8px 0; font-size: 15px; color: #e65100; font-weight: 600;">⏰ Action Required</p>
                        <p style="margin: 0; font-size: 14px; color: #333; line-height: 1.6;">
                            Please review this registration and approve or reject the account from your admin dashboard.
                        </p>
                    </div>

                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{dashboard_url}" style="background-color: #f58220; color: #fff; text-decoration: none; padding: 16px 40px; border-radius: 6px; font-weight: 600; display: inline-block; font-size: 16px; box-shadow: 0 2px 8px rgba(245, 130, 32, 0.3);">
                            Review in Dashboard →
                        </a>
                    </div>

                    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

                    <p style="font-size: 14px; color: #777; margin-bottom: 8px;">
                        If the button doesn't work, copy and paste this link into your browser:
                    </p>
                    <p style="word-break: break-all; font-size: 13px; background-color: #f8f9fa; padding: 10px; border-radius: 4px;">
                        <a href="{dashboard_url}" style="color: #f58220; text-decoration: none;">{dashboard_url}</a>
                    </p>

                    <p style="margin-top: 25px; font-size: 14px; color: #666;">
                        This is an automated notification from Tiger Leads.ai
                    </p>
                </div>

                <div style="background-color: #fafafa; text-align: center; padding: 20px; font-size: 12px; color: #777; border-top: 1px solid #eee;">
                    &copy; {year} Tiger Leads.ai. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """

    try:
        send_email_resend(admin_email, subject, html_content)
        logger.info(
            f"Admin notification email sent successfully to {admin_email} for new {role} registration: {user_email}"
        )
        return True, None
    except Exception as e:
        logger.error(
            f"Failed to send admin notification email to {admin_email}: {str(e)}"
        )
        return False, "Failed to send admin notification email"


async def send_subscription_thank_you_email(
    recipient_email: str, user_name: str, plan_name: str, credits: int, max_seats: int
):
    """Send thank you email when user purchases a subscription.

    Args:
        recipient_email: Email of the user who purchased
        user_name: Name of the user (company name or email)
        plan_name: Name of the subscription plan (e.g., "Starter", "Professional")
        credits: Number of credits in the plan
        max_seats: Number of seats in the plan

    Returns (True, None) on success or (False, error_message) on failure.
    """
    # Validate email
    is_valid, result = is_valid_email(recipient_email)
    if not is_valid:
        logger.error(f"Invalid email format: {recipient_email}")
        return False, "Please provide a valid email address format"

    subject = f"Thank You for Subscribing to {plan_name} – Tiger Leads.ai"
    year = datetime.utcnow().year

    # Try to load logo as base64
    logo_base64 = None
    if LOGO_PATH.exists():
        try:
            with open(LOGO_PATH, "rb") as img_file:
                logo_base64 = base64.b64encode(img_file.read()).decode("utf-8")
        except Exception:
            pass

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
                    <h2 style="color: #222; margin-top: 0;">🎉 Thank You for Your Subscription!</h2>
                    
                    <p style="line-height: 1.6; font-size: 16px;">
                        Hi <strong style="color: #f58220;">{user_name}</strong>,
                    </p>

                    <p style="line-height: 1.6; font-size: 16px;">
                        Thank you for subscribing to the <strong>{plan_name}</strong> plan on <strong>Tiger Leads.ai</strong>! 
                        We're thrilled to have you on board and can't wait to help you grow your business.
                    </p>

                    <div style="background-color: #fff3e0; border-left: 4px solid #f58220; padding: 20px; margin: 25px 0; border-radius: 6px;">
                        <p style="margin: 0 0 12px 0; font-size: 15px; color: #e65100; font-weight: 600;">📦 Your Subscription Details:</p>
                        <p style="margin: 0; font-size: 14px; color: #333; line-height: 1.8;">
                            <strong>Plan:</strong> <span style="color: #f58220; font-weight: 600;">{plan_name}</span><br>
                            <strong>Credits:</strong> {credits} credits per month<br>
                            <strong>Team Seats:</strong> {max_seats} seat{"s" if max_seats != 1 else ""}
                        </p>
                    </div>

                    <div style="background-color: #e8f5e9; border-radius: 6px; padding: 20px; margin: 25px 0;">
                        <p style="margin: 0 0 12px 0; font-weight: 600; color: #2e7d32; font-size: 15px;">✨ What You Can Do Now:</p>
                        <ul style="margin: 0; padding-left: 20px; line-height: 2;">
                            <li style="margin-bottom: 8px;">Access exclusive leads tailored to your business</li>
                            <li style="margin-bottom: 8px;">Connect with potential clients in your service area</li>
                            <li style="margin-bottom: 8px;">Invite team members to collaborate (up to {max_seats} seat{"s" if max_seats != 1 else ""})</li>
                            <li style="margin-bottom: 0;">Grow your business with Tiger Leads.ai</li>
                        </ul>
                    </div>

                    <div style="text-align: center; margin: 30px 0;">
                        <p style="font-size: 16px; color: #666; margin-bottom: 15px;">
                            Ready to get started?
                        </p>
                        <a href="{FRONTEND_URL}/dashboard" style="background-color: #f58220; color: #fff; text-decoration: none; padding: 16px 40px; border-radius: 6px; font-weight: 600; display: inline-block; font-size: 16px; box-shadow: 0 2px 8px rgba(245, 130, 32, 0.3);">
                            Go to Dashboard
                        </a>
                    </div>

                    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

                    <p style="margin-top: 30px; line-height: 1.6; color: #666;">
                        If you have any questions or need assistance, feel free to reply to this email or contact our support team. We're here to help!
                    </p>

                    <p style="margin-top: 25px;">Best regards,<br><strong style="color: #f58220;">The Tiger Leads.ai Team</strong></p>
                </div>

                <div style="background-color: #fafafa; text-align: center; padding: 20px; font-size: 12px; color: #777; border-top: 1px solid #eee;">
                    &copy; {year} Tiger Leads.ai. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """

    try:
        send_email_resend(recipient_email, subject, html_content)
        logger.info(
            f"Subscription thank you email sent successfully to {recipient_email} for {plan_name} plan via Resend"
        )
        return True, None
    except Exception as e:
        logger.error(
            f"Failed to send subscription thank you email to {recipient_email}: {str(e)}"
        )
        return False, "Failed to send subscription thank you email"


async def send_lead_unlock_email(
    recipient_email: str,
    user_name: str,
    job_title: str,
    job_location: str,
    credits_spent: int,
):
    """Send celebration email when user unlocks a lead/job.

    Args:
        recipient_email: Email of the user who unlocked the lead
        user_name: Name of the user (company name or email)
        job_title: Title of the unlocked job
        job_location: Location of the job
        credits_spent: Number of credits spent to unlock

    Returns (True, None) on success or (False, error_message) on failure.
    """
    # Validate email
    is_valid, result = is_valid_email(recipient_email)
    if not is_valid:
        logger.error(f"Invalid email format: {recipient_email}")
        return False, "Please provide a valid email address format"

    subject = f"🎉 You've Unlocked a New Lead – Tiger Leads.ai"
    year = datetime.utcnow().year

    # Try to load logo as base64
    logo_base64 = None
    if LOGO_PATH.exists():
        try:
            with open(LOGO_PATH, "rb") as img_file:
                logo_base64 = base64.b64encode(img_file.read()).decode("utf-8")
        except Exception:
            pass

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
                    <h2 style="color: #222; margin-top: 0;">🎉 Yay! You've Unlocked a New Lead!</h2>
                    
                    <p style="line-height: 1.6; font-size: 16px;">
                        Hi <strong style="color: #f58220;">{user_name}</strong>,
                    </p>

                    <p style="line-height: 1.6; font-size: 16px;">
                        Great news! You've successfully unlocked a new lead on <strong>Tiger Leads.ai</strong>. 
                        Here are the details:
                    </p>

                    <div style="background-color: #fff3e0; border-left: 4px solid #f58220; padding: 20px; margin: 25px 0; border-radius: 6px;">
                        <p style="margin: 0 0 12px 0; font-size: 15px; color: #e65100; font-weight: 600;">📋 Lead Details:</p>
                        <p style="margin: 0; font-size: 14px; color: #333; line-height: 1.8;">
                            <strong>Job:</strong> <span style="color: #f58220; font-weight: 600;">{job_title}</span><br>
                            <strong>Location:</strong> {job_location}<br>
                            <strong>Credits Spent:</strong> {credits_spent} credit{"s" if credits_spent != 1 else ""}
                        </p>
                    </div>

                    <div style="background-color: #e8f5e9; border-radius: 6px; padding: 20px; margin: 25px 0;">
                        <p style="margin: 0 0 12px 0; font-weight: 600; color: #2e7d32; font-size: 15px;">✨ What's Next?</p>
                        <ul style="margin: 0; padding-left: 20px; line-height: 2;">
                            <li style="margin-bottom: 8px;">Review the full lead details in your dashboard</li>
                            <li style="margin-bottom: 8px;">Contact the client to discuss the project</li>
                            <li style="margin-bottom: 8px;">Submit your proposal or quote</li>
                            <li style="margin-bottom: 0;">Win the project and grow your business!</li>
                        </ul>
                    </div>

                    <div style="text-align: center; margin: 30px 0;">
                        <p style="font-size: 16px; color: #666; margin-bottom: 15px;">
                            Ready to view your lead?
                        </p>
                        <a href="{FRONTEND_URL}/dashboard/unlocked-leads" style="background-color: #f58220; color: #fff; text-decoration: none; padding: 16px 40px; border-radius: 6px; font-weight: 600; display: inline-block; font-size: 16px; box-shadow: 0 2px 8px rgba(245, 130, 32, 0.3);">
                            View Lead Details
                        </a>
                    </div>

                    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

                    <div style="background-color: #fff3e0; border-radius: 6px; padding: 15px; margin: 20px 0;">
                        <p style="margin: 0; font-size: 14px; color: #e65100; line-height: 1.6;">
                            <strong>💡 Tip:</strong> Respond quickly to increase your chances of winning the project. Early responses often make the best impression!
                        </p>
                    </div>

                    <p style="margin-top: 30px; line-height: 1.6; color: #666;">
                        Good luck with your proposal! If you have any questions, feel free to reply to this email or contact our support team.
                    </p>

                    <p style="margin-top: 25px;">Best regards,<br><strong style="color: #f58220;">The Tiger Leads.ai Team</strong></p>
                </div>

                <div style="background-color: #fafafa; text-align: center; padding: 20px; font-size: 12px; color: #777; border-top: 1px solid #eee;">
                    &copy; {year} Tiger Leads.ai. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """

    try:
        send_email_resend(recipient_email, subject, html_content)
        logger.info(
            f"Lead unlock email sent successfully to {recipient_email} for job '{job_title}'"
        )
        return True, None
    except Exception as e:
        logger.error(f"Failed to send lead unlock email to {recipient_email}: {str(e)}")
        return False, "Failed to send lead unlock email"


async def send_jurisdiction_rejection_email(
    recipient_email: str,
    user_name: str,
    jurisdiction_type: str,
    jurisdiction_value: str,
    rejection_note: str = None,
):
    """Notify user of a rejected jurisdiction request."""
    subject = "Update Regarding Your Jurisdiction Request – Tiger Leads.ai"
    year = datetime.utcnow().year

    logo_base64 = None
    if LOGO_PATH.exists():
        try:
            with open(LOGO_PATH, "rb") as img_file:
                logo_base64 = base64.b64encode(img_file.read()).decode("utf-8")
        except Exception:
            pass

    logo_html = (
        f'<img src="data:image/png;base64,{logo_base64}" alt="Tiger Leads" style="width: 160px; height: auto;" />'
        if logo_base64
        else '<h1 style="color: #f58220; margin: 0;">Tiger Leads</h1>'
    )

    j_type_label = "State" if jurisdiction_type == "state" else "County/City"
    note_section = ""
    if rejection_note:
        note_section = f"""
            <div style="background-color: #fef2f2; border-left: 4px solid #ef4444; padding: 20px; margin: 25px 0; border-radius: 6px;">
                <p style="margin: 0 0 8px 0; font-size: 15px; color: #991b1b; font-weight: 600;">Admin Feedback:</p>
                <p style="margin: 0; font-size: 14px; color: #374151; line-height: 1.6;">{rejection_note}</p>
            </div>
        """

    html_content = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: 'Segoe UI', Roboto, Arial, sans-serif; background-color: #f9f9fb; color: #333; margin: 0; padding: 0;">
            <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); overflow: hidden;">
                <div style="background-color: #ffffff; text-align: center; padding: 25px 0; border-bottom: 1px solid #eee;">
                    {logo_html}
                </div>
                <div style="padding: 30px;">
                    <h2 style="color: #222; margin-top: 0;">Update on Your Request</h2>
                    <p style="line-height: 1.6; font-size: 16px;">Hi {user_name},</p>
                    <p style="line-height: 1.6; font-size: 16px;">
                        Thank you for your request to add <strong>{jurisdiction_value}</strong> ({j_type_label}) to your service area.
                    </p>
                    <p style="line-height: 1.6; font-size: 16px;">
                        After reviewing your request, our team is unable to approve this jurisdiction at this time.
                    </p>
                    {note_section}
                    <p style="line-height: 1.6; color: #666; font-size: 14px;">
                        If you believe this is an error or if you have updated information, please feel free to reach out to our support team.
                    </p>
                    <p style="margin-top: 25px;">Best regards,<br><strong style="color: #f58220;">The Tiger Leads.ai Team</strong></p>
                </div>
                <div style="background-color: #fafafa; text-align: center; padding: 20px; font-size: 12px; color: #777; border-top: 1px solid #eee;">
                    &copy; {year} Tiger Leads.ai. All rights reserved.
                </div>
            </div>
        </body>
        </html>
    """

    try:
        send_email_resend(recipient_email, subject, html_content)
        return True, None
    except Exception as e:
        logger.error(f"Failed to send jurisdiction rejection email: {str(e)}")
        return False, str(e)


async def send_category_rejection_email(
    recipient_email: str,
    user_name: str,
    category_value: str,
    rejection_note: str = None,
):
    """Notify user of a rejected category/trade request."""
    subject = "Update Regarding Your Trade Category Request – Tiger Leads.ai"
    year = datetime.utcnow().year

    logo_base64 = None
    if LOGO_PATH.exists():
        try:
            with open(LOGO_PATH, "rb") as img_file:
                logo_base64 = base64.b64encode(img_file.read()).decode("utf-8")
        except Exception:
            pass

    logo_html = (
        f'<img src="data:image/png;base64,{logo_base64}" alt="Tiger Leads" style="width: 160px; height: auto;" />'
        if logo_base64
        else '<h1 style="color: #f58220; margin: 0;">Tiger Leads</h1>'
    )

    note_section = ""
    if rejection_note:
        note_section = f"""
            <div style="background-color: #fef2f2; border-left: 4px solid #ef4444; padding: 20px; margin: 25px 0; border-radius: 6px;">
                <p style="margin: 0 0 8px 0; font-size: 15px; color: #991b1b; font-weight: 600;">Admin Feedback:</p>
                <p style="margin: 0; font-size: 14px; color: #374151; line-height: 1.6;">{rejection_note}</p>
            </div>
        """

    html_content = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: 'Segoe UI', Roboto, Arial, sans-serif; background-color: #f9f9fb; color: #333; margin: 0; padding: 0;">
            <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); overflow: hidden;">
                <div style="background-color: #ffffff; text-align: center; padding: 25px 0; border-bottom: 1px solid #eee;">
                    {logo_html}
                </div>
                <div style="padding: 30px;">
                    <h2 style="color: #222; margin-top: 0;">Update on Your Category Request</h2>
                    <p style="line-height: 1.6; font-size: 16px;">Hi {user_name},</p>
                    <p style="line-height: 1.6; font-size: 16px;">
                        Thank you for your request to add <strong>{category_value}</strong> to your profile categories.
                    </p>
                    <p style="line-height: 1.6; font-size: 16px;">
                        Our team has reviewed your request and is unable to approve this category at this time.
                    </p>
                    {note_section}
                    <p style="line-height: 1.6; color: #666; font-size: 14px;">
                        If you have supporting documentation or believe this to be an error, please contact our support team.
                    </p>
                    <p style="margin-top: 25px;">Best regards,<br><strong style="color: #f58220;">The Tiger Leads.ai Team</strong></p>
                </div>
                <div style="background-color: #fafafa; text-align: center; padding: 20px; font-size: 12px; color: #777; border-top: 1px solid #eee;">
                    &copy; {year} Tiger Leads.ai. All rights reserved.
                </div>
            </div>
        </body>
        </html>
    """

    try:
        send_email_resend(recipient_email, subject, html_content)
        return True, None
    except Exception as e:
        logger.error(f"Failed to send category rejection email: {str(e)}")
        return False, str(e)


async def send_account_rejection_email(
    recipient_email: str,
    user_name: str,
    role: str,
    rejection_note: str = None,
):
    """Notify user that their account application has been rejected."""
    subject = "Update Regarding Your Application – Tiger Leads.ai"
    year = datetime.utcnow().year

    logo_base64 = None
    if LOGO_PATH.exists():
        try:
            with open(LOGO_PATH, "rb") as img_file:
                logo_base64 = base64.b64encode(img_file.read()).decode("utf-8")
        except Exception:
            pass

    logo_html = (
        f'<img src="data:image/png;base64,{logo_base64}" alt="Tiger Leads" style="width: 160px; height: auto;" />'
        if logo_base64
        else '<h1 style="color: #f58220; margin: 0;">Tiger Leads</h1>'
    )

    note_section = ""
    if rejection_note:
        note_section = f"""
            <div style="background-color: #fef2f2; border-left: 4px solid #ef4444; padding: 20px; margin: 25px 0; border-radius: 6px;">
                <p style="margin: 0 0 8px 0; font-size: 15px; color: #991b1b; font-weight: 600;">Feedback from our team:</p>
                <p style="margin: 0; font-size: 14px; color: #374151; line-height: 1.6;">{rejection_note}</p>
            </div>
        """

    html_content = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: 'Segoe UI', Roboto, Arial, sans-serif; background-color: #f9f9fb; color: #333; margin: 0; padding: 0;">
            <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); overflow: hidden;">
                <div style="background-color: #ffffff; text-align: center; padding: 25px 0; border-bottom: 1px solid #eee;">
                    {logo_html}
                </div>
                <div style="padding: 30px;">
                    <h2 style="color: #222; margin-top: 0;">Tiger Leads Application Update</h2>
                    <p style="line-height: 1.6; font-size: 16px;">Hi {user_name},</p>
                    <p style="line-height: 1.6; font-size: 16px;">
                        Thank you for your interest in joining Tiger Leads.ai as a <strong>{role}</strong>.
                    </p>
                    <p style="line-height: 1.6; font-size: 16px;">
                        At this time, we are unable to approve your application to the platform.
                    </p>
                    {note_section}
                    <p style="line-height: 1.6; color: #666; font-size: 14px;">
                        If you have any questions, please contact our support team.
                    </p>
                    <p style="margin-top: 25px;">Best regards,<br><strong style="color: #f58220;">The Tiger Leads.ai Team</strong></p>
                </div>
                <div style="background-color: #fafafa; text-align: center; padding: 20px; font-size: 12px; color: #777; border-top: 1px solid #eee;">
                    &copy; {year} Tiger Leads.ai. All rights reserved.
                </div>
            </div>
        </body>
        </html>
    """

    try:
        send_email_resend(recipient_email, subject, html_content)
        return True, None
    except Exception as e:
        logger.error(f"Failed to send account rejection email: {str(e)}")
        return False, str(e)


async def send_account_approval_email(
    recipient_email: str,
    user_name: str,
    role: str,
    login_url: str,
    approval_note: str = None,
):
    """Notify user that their account has been approved."""
    subject = "🎉 Your Account Has Been Approved – Tiger Leads.ai"
    year = datetime.utcnow().year

    logo_base64 = None
    if LOGO_PATH.exists():
        try:
            with open(LOGO_PATH, "rb") as img_file:
                logo_base64 = base64.b64encode(img_file.read()).decode("utf-8")
        except Exception:
            pass

    logo_html = (
        f'<img src="data:image/png;base64,{logo_base64}" alt="Tiger Leads" style="width: 160px; height: auto;" />'
        if logo_base64
        else '<h1 style="color: #f58220; margin: 0;">Tiger Leads</h1>'
    )

    note_section = ""
    if approval_note:
        note_section = f"""
            <div style="background-color: #f0fdf4; border-left: 4px solid #10b981; padding: 20px; margin: 25px 0; border-radius: 6px;">
                <p style="margin: 0 0 8px 0; font-size: 15px; color: #065f46; font-weight: 600;">Message from our team:</p>
                <p style="margin: 0; font-size: 14px; color: #374151; line-height: 1.6;">{approval_note}</p>
            </div>
        """

    html_content = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: 'Segoe UI', Roboto, Arial, sans-serif; background-color: #f9f9fb; color: #333; margin: 0; padding: 0;">
            <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); overflow: hidden;">
                <div style="background-color: #ffffff; text-align: center; padding: 25px 0; border-bottom: 1px solid #eee;">
                    {logo_html}
                </div>
                <div style="padding: 30px;">
                    <h2 style="color: #10b981; margin-top: 0;">🎉 Congratulations! Your Account is Approved!</h2>
                    <p style="line-height: 1.6; font-size: 16px;">Hi {user_name},</p>
                    <p style="line-height: 1.6; font-size: 16px;">
                        Great news! Your <strong>{role}</strong> account on Tiger Leads.ai has been approved by our team.
                    </p>
                    <p style="line-height: 1.6; font-size: 16px;">
                        You now have full access to the platform and can start exploring exclusive leads!
                    </p>
                    {note_section}
                    <div style="background-color: #f0fdf4; border-left: 4px solid #10b981; padding: 20px; margin: 25px 0; border-radius: 6px;">
                        <p style="margin: 0 0 12px 0; font-size: 15px; color: #065f46; font-weight: 600;">What You Can Do Now:</p>
                        <ul style="margin: 0; padding-left: 20px; color: #374151; font-size: 14px; line-height: 1.8;">
                            <li>Access exclusive construction leads in your area</li>
                            <li>Connect with potential clients and projects</li>
                            <li>Manage your profile and preferences</li>
                            <li>Unlock leads and grow your business</li>
                            <li>Explore all platform features</li>
                        </ul>
                    </div>
                    <p style="line-height: 1.6; font-size: 16px; margin-top: 25px;">
                        <strong>Ready to get started?</strong>
                    </p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{login_url}" style="display: inline-block; background-color: #f58220; color: #ffffff; text-decoration: none; padding: 14px 32px; border-radius: 6px; font-weight: 600; font-size: 16px;">
                            Login to Your Account →
                        </a>
                    </div>
                    <p style="line-height: 1.6; color: #666; font-size: 14px;">
                        Or copy and paste this link into your browser:<br>
                        <a href="{login_url}" style="color: #f58220; word-break: break-all;">{login_url}</a>
                    </p>
                    <p style="line-height: 1.6; color: #666; font-size: 14px; margin-top: 25px;">
                        If you have any questions or need assistance, our support team is here to help!
                    </p>
                    <p style="margin-top: 25px;">Best regards,<br><strong style="color: #f58220;">The Tiger Leads.ai Team</strong></p>
                </div>
                <div style="background-color: #fafafa; text-align: center; padding: 20px; font-size: 12px; color: #777; border-top: 1px solid #eee;">
                    &copy; {year} Tiger Leads.ai. All rights reserved.
                </div>
            </div>
        </body>
        </html>
    """

    try:
        send_email_resend(recipient_email, subject, html_content)
        logger.info(f"Account approval email sent successfully to {recipient_email} for {role}")
        return True, None
    except Exception as e:
        logger.error(f"Failed to send account approval email to {recipient_email}: {str(e)}")
        return False, str(e)



async def send_job_rejection_email(
    contractor_email: str,
    contractor_name: str,
    job_data: dict,
    decline_reasons: list[str],
    admin_note: str = None,
):
    """Send job rejection email to contractor with rejection reasons and job details.
    
    Args:
        contractor_email: Contractor's email address
        contractor_name: Contractor's name
        job_data: Dictionary containing job details (permit_number, job_address, etc.)
        decline_reasons: List of rejection reason codes
        admin_note: Optional custom note from admin
    
    Returns:
        (True, None) on success or (False, error_message) on failure
    """
    # Validate email
    is_valid, result = is_valid_email(contractor_email)
    if not is_valid:
        logger.error(f"Invalid contractor email format: {contractor_email}")
        return False, "Invalid contractor email address"

    subject = "Job Posting Declined - Action Required"
    year = datetime.utcnow().year

    # Map reason codes to full descriptions
    reason_descriptions = {
        "out_of_service_area": "Out of Service Area - Project location is outside our current service areas",
        "project_type_not_supported": "Project Type Not Supported - This type of project is not currently supported on our platform",
        "insufficient_project_value": "Insufficient Project Value - Project cost is below the minimum threshold for our platform",
        "missing_required_documents": "Missing Required Documents - Supporting documents (permits, licenses, or project plans) are required but not provided",
        "incomplete_documentation": "Incomplete Documentation - Uploaded documents are unclear, illegible, or missing critical information",
        "invalid_document_format": "Invalid Document Format - Documents must be in PDF, JPG, or PNG format",
        "invalid_expired_license": "Invalid or Expired License - Contractor license information could not be verified or has expired",
        "license_mismatch": "License Mismatch - License type doesn't match the project type or jurisdiction",
        "missing_insurance": "Missing Insurance Information - Required insurance documentation not provided",
        "incomplete_project_info": "Incomplete Project Information - Critical fields (address, description, cost, etc.) are missing or insufficient",
        "inaccurate_details": "Inaccurate Project Details - Project information appears incorrect or inconsistent",
        "invalid_contact_info": "Invalid Contact Information - Email or phone number format is invalid or unreachable",
    }

    # Build reasons HTML list
    reasons_html = ""
    for reason_code in decline_reasons:
        reason_text = reason_descriptions.get(reason_code, reason_code)
        reasons_html += f'<li style="margin-bottom: 8px; color: #DC2626; font-weight: 500;">{reason_text}</li>'

    # Build user types table rows
    user_types_rows = ""
    if job_data.get("user_types"):
        for ut in job_data["user_types"]:
            user_types_rows += f"""
            <tr>
                <td style="padding: 12px; border-bottom: 1px solid #E5E7EB;">{ut.get('audience_type_names', 'N/A')}</td>
                <td style="padding: 12px; border-bottom: 1px solid #E5E7EB; text-align: center;">{ut.get('offset_days', 0)} days</td>
            </tr>
            """

    # Admin note section
    admin_note_html = ""
    if admin_note:
        admin_note_html = f"""
        <div style="background-color: #FEF3C7; border-left: 4px solid #F59E0B; padding: 16px; margin: 24px 0; border-radius: 4px;">
            <p style="margin: 0; font-weight: 600; color: #92400E; margin-bottom: 8px;">Additional Note from Admin:</p>
            <p style="margin: 0; color: #78350F;">{admin_note}</p>
        </div>
        """

    # Try to load logo as base64
    logo_base64 = None
    if LOGO_PATH.exists():
        try:
            with open(LOGO_PATH, "rb") as f:
                logo_base64 = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            logger.warning(f"Could not load logo: {e}")

    logo_html = ""
    if logo_base64:
        logo_html = f'<img src="data:image/png;base64,{logo_base64}" alt="Tiger Leads.ai" style="height: 40px; margin-bottom: 20px;" />'

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #F3F4F6;">
        <table role="presentation" style="width: 100%; border-collapse: collapse;">
            <tr>
                <td align="center" style="padding: 40px 20px;">
                    <table role="presentation" style="max-width: 600px; width: 100%; background-color: #FFFFFF; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                        <!-- Header -->
                        <tr>
                            <td style="padding: 40px 40px 20px 40px; text-align: center;">
                                {logo_html}
                                <h1 style="margin: 0; font-size: 24px; font-weight: 700; color: #111827;">Job Posting Declined</h1>
                            </td>
                        </tr>
                        
                        <!-- Content -->
                        <tr>
                            <td style="padding: 0 40px 40px 40px;">
                                <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 24px; color: #374151;">
                                    Hi {contractor_name},
                                </p>
                                
                                <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 24px; color: #374151;">
                                    Unfortunately, your job posting has been declined by our admin team. Please review the reasons below and resubmit your job with the necessary corrections.
                                </p>

                                <!-- Rejection Reasons -->
                                <div style="background-color: #FEE2E2; border-left: 4px solid #DC2626; padding: 16px; margin: 24px 0; border-radius: 4px;">
                                    <p style="margin: 0 0 12px 0; font-weight: 600; color: #991B1B; font-size: 16px;">Reasons for Decline:</p>
                                    <ul style="margin: 0; padding-left: 20px; color: #7F1D1D;">
                                        {reasons_html}
                                    </ul>
                                </div>

                                {admin_note_html}

                                <!-- Job Details -->
                                <div style="background-color: #F9FAFB; padding: 20px; border-radius: 6px; margin: 24px 0;">
                                    <h2 style="margin: 0 0 16px 0; font-size: 18px; font-weight: 600; color: #111827;">Job Details</h2>
                                    
                                    <table style="width: 100%; border-collapse: collapse;">
                                        <tr>
                                            <td style="padding: 8px 0; font-weight: 600; color: #6B7280; width: 40%;">Permit Number:</td>
                                            <td style="padding: 8px 0; color: #111827;">{job_data.get('permit_number', 'N/A')}</td>
                                        </tr>
                                        <tr>
                                            <td style="padding: 8px 0; font-weight: 600; color: #6B7280;">Job Address:</td>
                                            <td style="padding: 8px 0; color: #111827;">{job_data.get('job_address', 'N/A')}</td>
                                        </tr>
                                        <tr>
                                            <td style="padding: 8px 0; font-weight: 600; color: #6B7280;">Property Type:</td>
                                            <td style="padding: 8px 0; color: #111827;">{job_data.get('property_type', 'N/A')}</td>
                                        </tr>
                                        <tr>
                                            <td style="padding: 8px 0; font-weight: 600; color: #6B7280;">Project Cost:</td>
                                            <td style="padding: 8px 0; color: #111827;">${job_data.get('project_cost_total', 0):,.2f}</td>
                                        </tr>
                                        <tr>
                                            <td style="padding: 8px 0; font-weight: 600; color: #6B7280;">Description:</td>
                                            <td style="padding: 8px 0; color: #111827;">{job_data.get('project_description', 'N/A')[:100]}...</td>
                                        </tr>
                                    </table>
                                </div>

                                <!-- User Types & Offset Days -->
                                {f'''
                                <div style="margin: 24px 0;">
                                    <h2 style="margin: 0 0 16px 0; font-size: 18px; font-weight: 600; color: #111827;">Target User Types & Visibility Schedule</h2>
                                    <table style="width: 100%; border-collapse: collapse; border: 1px solid #E5E7EB; border-radius: 6px; overflow: hidden;">
                                        <thead>
                                            <tr style="background-color: #F3F4F6;">
                                                <th style="padding: 12px; text-align: left; font-weight: 600; color: #374151; border-bottom: 2px solid #E5E7EB;">User Type</th>
                                                <th style="padding: 12px; text-align: center; font-weight: 600; color: #374151; border-bottom: 2px solid #E5E7EB;">Show After</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {user_types_rows}
                                        </tbody>
                                    </table>
                                </div>
                                ''' if user_types_rows else ''}

                                <!-- Next Steps -->
                                <div style="background-color: #EFF6FF; border-left: 4px solid #3B82F6; padding: 16px; margin: 24px 0; border-radius: 4px;">
                                    <p style="margin: 0 0 12px 0; font-weight: 600; color: #1E40AF; font-size: 16px;">What to Do Next:</p>
                                    <ol style="margin: 0; padding-left: 20px; color: #1E3A8A;">
                                        <li style="margin-bottom: 8px;">Review the rejection reasons above</li>
                                        <li style="margin-bottom: 8px;">Make the necessary corrections to your job posting</li>
                                        <li style="margin-bottom: 8px;">Resubmit your job through your dashboard</li>
                                    </ol>
                                </div>

                                <!-- CTA Button -->
                                <div style="text-align: center; margin: 32px 0;">
                                    <a href="{FRONTEND_URL}/contractor/my-jobs" 
                                       style="display: inline-block; padding: 14px 32px; background-color: #F97316; color: #FFFFFF; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 16px;">
                                        View My Jobs
                                    </a>
                                </div>

                                <p style="margin: 24px 0 0 0; font-size: 14px; line-height: 20px; color: #6B7280;">
                                    If you have questions about this decision, please contact our support team.
                                </p>
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td style="padding: 20px 40px; background-color: #F9FAFB; border-top: 1px solid #E5E7EB; text-align: center;">
                                <p style="margin: 0; font-size: 12px; color: #6B7280;">
                                    © {year} Tiger Leads.ai. All rights reserved.
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    try:
        success = await send_email_resend(
            to_email=contractor_email,
            subject=subject,
            html_content=html_body,
        )
        if success:
            logger.info(f"Job rejection email sent successfully to {contractor_email}")
            return True, None
        else:
            logger.error(f"Failed to send job rejection email to {contractor_email}")
            return False, "Failed to send email"
    except Exception as e:
        logger.error(f"Error sending job rejection email: {str(e)}")
        return False, str(e)
