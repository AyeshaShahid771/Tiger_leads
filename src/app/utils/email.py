import base64
import logging
import os
import re
from datetime import datetime
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import aiosmtplib
from dotenv import load_dotenv
from email_validator import EmailNotValidError, validate_email

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Define logo path
LOGO_PATH = Path.cwd() / "src" / "public" / "logo.png"


def is_valid_email(email: str) -> tuple[bool, str]:
    try:
        # Check email format and DNS using email-validator
        validation = validate_email(email, check_deliverability=True)
        normalized_email = validation.email

        return True, normalized_email

        return True, normalized_email
    except EmailNotValidError as e:
        return False, str(e)
    except Exception as e:
        logger.error(f"Error validating email {email}: {str(e)}")
        return False, "Email validation failed, please try again"


async def send_verification_email(recipient_email: str, code: str):
    """Send verification code email with inline (CID) logo image using async SMTP.

    Uses `src/public/logo.png` as the embedded image. Returns (True, None) or (False, error).
    """
    # First validate email format
    is_valid, result = is_valid_email(recipient_email)
    if not is_valid:
        logger.error(f"Invalid email format: {recipient_email}")
        return False, "Please provide a valid email address format"

    subject = "Verify Your Email – Tiger Leads.ai"
    year = datetime.utcnow().year

    # Try to load logo as base64 for Vercel compatibility
    logo_base64 = None
    if LOGO_PATH.exists():
        try:
            with open(LOGO_PATH, "rb") as img_file:
                logo_base64 = base64.b64encode(img_file.read()).decode("utf-8")
                logger.info(f"Logo loaded as base64 from: {LOGO_PATH}")
        except Exception as e:
            logger.error(f"Error reading logo from {LOGO_PATH}: {str(e)}")
    else:
        logger.warning(f"Logo file not found at {LOGO_PATH}; using fallback")

    # Create message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = (
        f"Tiger Leads.ai <{os.getenv('EMAIL_FROM', os.getenv('SMTP_USER', 'no-reply@tigerleads.com'))}>"
    )
    msg["To"] = recipient_email

    # HTML content with base64 embedded image or fallback text
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

    # Attach the HTML content
    msg.attach(MIMEText(html_content, "html"))

    # Read SMTP configuration from environment
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 465))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    use_tls = smtp_port == 465

    try:
        logger.info(
            f"Setting up SMTP connection for {recipient_email} using {smtp_server}:{smtp_port}"
        )
        if use_tls:
            async with aiosmtplib.SMTP(
                hostname=smtp_server, port=smtp_port, use_tls=True
            ) as server:
                if smtp_user and smtp_pass:
                    logger.info("Attempting SMTP login")
                    await server.login(smtp_user, smtp_pass)
                logger.info(f"Sending verification email to {recipient_email}")
                await server.send_message(msg)
                logger.info(f"Email sent successfully to {recipient_email}")
                return True, None
        else:
            async with aiosmtplib.SMTP(
                hostname=smtp_server, port=smtp_port, start_tls=True
            ) as server:
                if smtp_user and smtp_pass:
                    logger.info("Attempting SMTP login")
                    await server.login(smtp_user, smtp_pass)
                logger.info(f"Sending verification email to {recipient_email}")
                await server.send_message(msg)
                logger.info(f"Email sent successfully to {recipient_email}")
                return True, None

    except aiosmtplib.SMTPRecipientsRefused as e:
        error_msg = "Invalid email address: This email address does not exist"
        logger.error(f"Recipients refused for {recipient_email}: {str(e)}")
        return False, error_msg
    except aiosmtplib.SMTPResponseException as e:
        if "550" in str(e):  # SMTP 550 typically means user not found
            error_msg = "Invalid email address: This email address does not exist"
        else:
            error_msg = "Failed to deliver email. Please try again later."
        logger.error(f"SMTP Response error for {recipient_email}: {str(e)}")
        return False, error_msg
    except aiosmtplib.SMTPAuthenticationError:
        error_msg = "Email service authentication failed. Please contact support."
        logger.error("SMTP authentication failed. Check sender email credentials")
        return False, error_msg
    except aiosmtplib.SMTPException as e:
        if "not found" in str(e).lower() or "no such user" in str(e).lower():
            error_msg = "Invalid email address: This email address does not exist"
        else:
            error_msg = "Failed to send email. Please try again later."
        logger.error(f"SMTP Error for {recipient_email}: {str(e)}")
        return False, error_msg
    except Exception as e:
        error_msg = "An unexpected error occurred while sending the email"
        logger.error(f"Unexpected error for {recipient_email}: {str(e)}")
        return False, error_msg


async def send_team_invitation_email(
    recipient_email: str, inviter_name: str, invitation_token: str, frontend_url: str
):
    """Send team invitation email to a new team member.

    Args:
        recipient_email: Email of the person being invited
        inviter_name: Name/email of the person sending the invitation
        invitation_token: Unique token for the signup link (not used in URL)
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
    signup_link = f"{frontend_url}/signup"

    # Try to load logo as base64
    logo_base64 = None
    if LOGO_PATH.exists():
        try:
            with open(LOGO_PATH, "rb") as img_file:
                logo_base64 = base64.b64encode(img_file.read()).decode("utf-8")
                logger.info(f"Logo loaded as base64 from: {LOGO_PATH}")
        except Exception as e:
            logger.error(f"Error reading logo from {LOGO_PATH}: {str(e)}")
    else:
        logger.warning(f"Logo file not found at {LOGO_PATH}; using fallback")

    # Create message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = (
        f"Tiger Leads.ai <{os.getenv('EMAIL_FROM', os.getenv('SMTP_USER', 'no-reply@tigerleads.com'))}>"
    )
    msg["To"] = recipient_email

    # HTML content with base64 embedded image or fallback text
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
                    <h2 style="color: #222;">You're Invited to Join a Team!</h2>
                    <p style="line-height: 1.6;">
                        Hi there,
                    </p>
                    <p style="line-height: 1.6;">
                        <strong>{inviter_name}</strong> has invited you to join their team on <strong>Tigerleads.ai</strong>
                    </p>

                    <div style="background-color: #f8f9fa; border-left: 4px solid #f58220; padding: 15px; margin: 20px 0;">
                        <p style="margin: 0; font-size: 14px; color: #666;">📧 Your invitation email:</p>
                        <p style="margin: 5px 0 0 0; font-size: 16px; color: #222; font-weight: 600;">{recipient_email}</p>
                    </div>

                    <p style="line-height: 1.6;">
                        To accept the invitation and create your account, click below:
                    </p>

                    <div style="text-align: center; margin: 25px 0;">
                        <a href="{signup_link}" style="background-color: #f58220; color: #fff; text-decoration: none; padding: 14px 30px; border-radius: 6px; font-weight: 600; display: inline-block; font-size: 16px;">
                            Accept Invitation & Sign Up
                        </a>
                    </div>

                    <div style="background-color: #e8f5e9; border-radius: 6px; padding: 15px; margin: 20px 0;">
                        <p style="margin: 0 0 10px 0; font-weight: 600; color: #2e7d32;">✨ What to expect:</p>
                        <ul style="margin: 0; padding-left: 20px; line-height: 1.8;">
                            <li>Sign up using this email: <strong>{recipient_email}</strong></li>
                            <li>Create your password</li>
                            <li>Access the shared team dashboard</li>
                            <li>Start working with leads immediately</li>
                        </ul>
                    </div>

                    <p style="line-height: 1.6; color: #d35400; font-weight: 600;">
                        ⚠️ Important: You must sign up using the email address <strong>{recipient_email}</strong> to accept this invitation.
                    </p>

                    <p style="line-height: 1.6; color: #666;">
                        <strong>Good news:</strong> This invitation never expires. Simply sign up whenever you're ready to join!
                    </p>

                    <hr style="border: none; border-top: 1px solid #eee; margin: 25px 0;">

                    <p style="font-size: 14px; color: #777;">
                        If the button doesn't work, copy and paste this link into your browser:
                    </p>
                    <p style="word-break: break-all; font-size: 13px;">
                        <a href="{signup_link}" style="color: #f58220;">{signup_link}</a>
                    </p>

                    <p style="margin-top: 30px; line-height: 1.6;">
                        Questions? Reply to this email or contact our support team.
                    </p>

                    <p>Best regards,<br><strong>The Tigerleads.ai Team</strong></p>
                </div>

                <div style="background-color: #fafafa; text-align: center; padding: 15px; font-size: 12px; color: #777; border-top: 1px solid #eee;">
                    &copy; {year} Tiger Leads.ai. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """

    # Attach the HTML content
    msg.attach(MIMEText(html_content, "html"))

    # Send via aiosmtplib
    try:
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", 465))
        smtp_user = os.getenv("SMTP_USER")
        smtp_pass = os.getenv("SMTP_PASSWORD")
        use_tls = smtp_port == 465

        logger.info(
            f"Sending team invitation email to {recipient_email} via {smtp_server}:{smtp_port}"
        )

        if use_tls:
            async with aiosmtplib.SMTP(
                hostname=smtp_server, port=smtp_port, use_tls=True
            ) as server:
                if smtp_user and smtp_pass:
                    await server.login(smtp_user, smtp_pass)
                await server.send_message(msg)
                logger.info(
                    f"Team invitation email sent successfully to {recipient_email}"
                )
                return True, None
        else:
            async with aiosmtplib.SMTP(
                hostname=smtp_server, port=smtp_port, start_tls=True
            ) as server:
                if smtp_user and smtp_pass:
                    await server.login(smtp_user, smtp_pass)
                await server.send_message(msg)
                logger.info(
                    f"Team invitation email sent successfully to {recipient_email}"
                )
                return True, None

    except aiosmtplib.SMTPRecipientsRefused as e:
        error_msg = "Invalid email address: This email address does not exist"
        logger.error(
            f"Recipients refused for invitation to {recipient_email}: {str(e)}"
        )
        return False, error_msg
    except aiosmtplib.SMTPResponseException as e:
        if "550" in str(e):
            error_msg = "Invalid email address: This email address does not exist"
        else:
            error_msg = "Failed to deliver email. Please try again later."
        logger.error(
            f"SMTP Response error for invitation to {recipient_email}: {str(e)}"
        )
        return False, error_msg
    except aiosmtplib.SMTPAuthenticationError as e:
        error_msg = "Email service authentication failed. Please contact support."
        logger.error(f"SMTP authentication failed for invitation: {str(e)}")
        return False, error_msg
    except aiosmtplib.SMTPException as e:
        if "not found" in str(e).lower() or "no such user" in str(e).lower():
            error_msg = "Invalid email address: This email address does not exist"
        else:
            error_msg = "Failed to send email. Please try again later."
        logger.error(f"SMTP Error for invitation to {recipient_email}: {str(e)}")
        return False, error_msg
    except Exception as e:
        error_msg = "An unexpected error occurred while sending the email"
        logger.error(
            f"Unexpected error sending invitation to {recipient_email}: {str(e)}"
        )
        return False, error_msg


async def send_password_reset_email(recipient_email: str, reset_link: str):
    """Send password reset email with inline (CID) logo image using async SMTP.

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
                logger.info(f"Logo loaded as base64 from: {LOGO_PATH}")
        except Exception as e:
            logger.error(f"Error reading logo from {LOGO_PATH}: {str(e)}")
    else:
        logger.warning(f"Logo file not found at {LOGO_PATH}; using fallback")

    # Create message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = (
        f"Tiger Leads.ai <{os.getenv('EMAIL_FROM', os.getenv('SMTP_USER', 'no-reply@tigerleads.com'))}>"
    )
    msg["To"] = recipient_email

    # HTML content with base64 embedded image or fallback text
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
                        If the button doesn’t work, copy and paste this link into your browser:
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

    # Attach the HTML content
    msg.attach(MIMEText(html_content, "html"))

    # Send via aiosmtplib
    try:
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", 465))
        smtp_user = os.getenv("SMTP_USER")
        smtp_pass = os.getenv("SMTP_PASSWORD")

        # Use implicit TLS (SMTPS) for port 465, otherwise use STARTTLS
        use_tls = smtp_port == 465

        logger.info(
            f"Sending password reset email to {recipient_email} via {smtp_server}:{smtp_port} (use_tls={use_tls})"
        )

        if use_tls:
            async with aiosmtplib.SMTP(
                hostname=smtp_server, port=smtp_port, use_tls=True
            ) as server:
                if smtp_user and smtp_pass:
                    logger.info("Attempting SMTP login for password reset")
                    await server.login(smtp_user, smtp_pass)
                logger.info(f"Sending password reset email to {recipient_email}")
                await server.send_message(msg)
                logger.info(
                    f"Password reset email sent successfully to {recipient_email}"
                )
                return True, None
        else:
            async with aiosmtplib.SMTP(
                hostname=smtp_server, port=smtp_port, start_tls=True
            ) as server:
                if smtp_user and smtp_pass:
                    logger.info("Attempting SMTP login for password reset")
                    await server.login(smtp_user, smtp_pass)
                logger.info(f"Sending password reset email to {recipient_email}")
                await server.send_message(msg)
                logger.info(
                    f"Password reset email sent successfully to {recipient_email}"
                )
                return True, None

    except aiosmtplib.SMTPRecipientsRefused as e:
        error_msg = "Invalid email address: This email address does not exist"
        logger.error(
            f"Recipients refused for password reset to {recipient_email}: {str(e)}"
        )
        return False, error_msg
    except aiosmtplib.SMTPResponseException as e:
        if "550" in str(e):
            error_msg = "Invalid email address: This email address does not exist"
        else:
            error_msg = "Failed to deliver email. Please try again later."
        logger.error(
            f"SMTP Response error for password reset to {recipient_email}: {str(e)}"
        )
        return False, error_msg
    except aiosmtplib.SMTPAuthenticationError as e:
        error_msg = "Email service authentication failed. Please contact support."
        logger.error(f"SMTP authentication failed for password reset: {str(e)}")
        return False, error_msg
    except aiosmtplib.SMTPException as e:
        if "not found" in str(e).lower() or "no such user" in str(e).lower():
            error_msg = "Invalid email address: This email address does not exist"
        else:
            error_msg = "Failed to send email. Please try again later."
        logger.error(f"SMTP Error for password reset to {recipient_email}: {str(e)}")
        return False, error_msg
    except Exception as e:
        error_msg = "An unexpected error occurred while sending the email"
        logger.error(
            f"Unexpected error sending password reset to {recipient_email}: {str(e)}"
        )
        return False, error_msg
