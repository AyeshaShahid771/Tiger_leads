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

# Email validation helper
def is_valid_email(email: str) -> tuple[bool, str | None]:  # type: ignore
    """Validate email format. Returns (is_valid, error_message)."""
    if not email or not isinstance(email, str):
        return False, "Email must be a non-empty string"
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
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

    html_content = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <div style="max-width:600px;margin:30px auto;background:#fff;padding:24px;border-radius:8px;">
                <div style="text-align:center;padding-bottom:12px;">{logo_html}</div>
                <h2 style="color:#222;margin-top:0;">You're invited to join Tiger Leads.ai</h2>
                <p>{inviter_name} has invited you to join as an <strong>{role}</strong>.</p>
                <p>Use the link below to accept the invitation and complete admin signup:</p>
                <div style="text-align:center;margin:20px 0;"><a href="{signup_link}" style="background:#f58220;color:#fff;padding:12px 20px;border-radius:6px;text-decoration:none;">Accept Invitation</a></div>
                <p style="font-size:13px;color:#666;">If the button doesn't work, copy-paste this URL into your browser:</p>
                <p style="word-break:break-all;background:#f8f9fa;padding:10px;border-radius:4px;color:#f58220;">{signup_link}</p>
                <p style="font-size:13px;color:#666;">Or use this token during signup: <strong>{token}</strong></p>
                <p>Thanks,<br>The Tiger Leads.ai Team</p>
                <div style="font-size:12px;color:#999;margin-top:18px;">&copy; {year} Tiger Leads.ai</div>
            </div>
        </body>
        </html>
    """

    try:
        send_email_resend(recipient_email, subject, html_content)
        logger.info(f"Admin invitation email sent successfully to {recipient_email} via Resend")
        return True, None
    except Exception as e:
        logger.exception("Failed to send admin invitation to %s: %s", recipient_email, e)
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
        logger.info(f"Verification email sent successfully to {recipient_email} via Resend")
        return True, None
    except Exception as e:
        logger.error(f"Failed to send verification email to {recipient_email}: {str(e)}")
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
        logger.info(f"Team invitation email sent successfully to {recipient_email} via Resend")
        return True, None
    except Exception as e:
        logger.error(f"Failed to send team invitation email to {recipient_email}: {str(e)}")
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
        logger.info(f"Password reset email sent successfully to {recipient_email} via Resend")
        return True, None
    except Exception as e:
        logger.error(f"Failed to send password reset email to {recipient_email}: {str(e)}")
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

                    <div style="background-color: #fff3e0; border-radius: 6px; padding: 15px; margin: 20px 0;">
                        <p style="margin: 0; font-size: 14px; color: #e65100; line-height: 1.6;">
                            <strong>💡 Tip:</strong> While you wait for approval, make sure your email address <strong>{recipient_email}</strong> is correct, 
                            as we'll use it to notify you about your account status.
                        </p>
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
        logger.info(f"Registration completion email sent successfully to {recipient_email} for {role} via Resend")
        return True, None
    except Exception as e:
        logger.error(f"Failed to send registration completion email to {recipient_email}: {str(e)}")
        return False, "Failed to send registration completion email"

