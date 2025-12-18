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
    # Prefer explicit EMAIL_FROM, but set Sender to the authenticated SMTP user
    smtp_user = os.getenv("SMTP_USER")
    email_from = os.getenv("EMAIL_FROM") or smtp_user or "no-reply@tigerleads.com"
    msg["From"] = f"Tiger Leads.ai <{email_from}>"
    if smtp_user and smtp_user != email_from:
        # Some providers (Gmail/Google Workspace) require the envelope sender
        # to match the authenticated user or a verified 'send as' address.
        msg["Sender"] = smtp_user
        logger.warning(
            "Email From (%s) differs from SMTP user (%s). Set up 'Send as' or use same address to improve deliverability.",
            email_from,
            smtp_user,
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

    # Optional debug BCC - set an env var `EMAIL_DEBUG_BCC` to receive copies for troubleshooting
    debug_bcc = os.getenv("EMAIL_DEBUG_BCC")
    recipients = [recipient_email]
    if debug_bcc:
        recipients.append(debug_bcc)
        # Add Bcc header for visibility in the message (SMTP will use recipients list)
        msg["Bcc"] = debug_bcc

    try:
        logger.info(
            f"Setting up SMTP connection for {recipient_email} using {smtp_server}:{smtp_port}"
        )
        if use_tls:
            async with aiosmtplib.SMTP(
                hostname=smtp_server, port=smtp_port, use_tls=True, timeout=30
            ) as server:
                if smtp_user and smtp_pass:
                    logger.info("Attempting SMTP login")
                    await server.login(smtp_user, smtp_pass)
                logger.info(
                    f"Sending verification email to {recipient_email} (recipients={recipients})"
                )
                send_result = await server.send_message(msg, recipients=recipients)
                logger.info(
                    "Email sent successfully to %s. SMTP response: %s",
                    recipients,
                    send_result,
                )
                return True, None
        else:
            async with aiosmtplib.SMTP(
                hostname=smtp_server, port=smtp_port, start_tls=True, timeout=30
            ) as server:
                if smtp_user and smtp_pass:
                    logger.info("Attempting SMTP login")
                    await server.login(smtp_user, smtp_pass)
                logger.info(
                    f"Sending verification email to {recipient_email} (recipients={recipients})"
                )
                send_result = await server.send_message(msg, recipients=recipients)
                logger.info(
                    "Email sent successfully to %s. SMTP response: %s",
                    recipients,
                    send_result,
                )
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
                logger.info(f"Logo loaded as base64 from: {LOGO_PATH}")
        except Exception as e:
            logger.error(f"Error reading logo from {LOGO_PATH}: {str(e)}")
    else:
        logger.warning(f"Logo file not found at {LOGO_PATH}; using fallback")

    # Create message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject

    # Prefer explicit EMAIL_FROM, but set Sender to the authenticated SMTP user
    smtp_user = os.getenv("SMTP_USER")
    email_from = os.getenv("EMAIL_FROM") or smtp_user or "no-reply@tigerleads.com"

    # IMPORTANT: For Gmail, the From address should match the authenticated SMTP user
    # to avoid being marked as spam or rejected
    if not smtp_user or email_from == smtp_user:
        msg["From"] = f"Tiger Leads.ai <{email_from}>"
    else:
        # Use SMTP user as From to match authenticated account
        msg["From"] = f"Tiger Leads.ai <{smtp_user}>"
        logger.info(
            "Using SMTP authenticated user (%s) as From address for better deliverability with Gmail",
            smtp_user,
        )

    msg["To"] = recipient_email
    msg["Reply-To"] = email_from  # Allow replies

    # Add Message-ID for better email tracking and deliverability
    import uuid

    msg["Message-ID"] = f"<{uuid.uuid4()}@tigerleads.com>"

    # Add X-Mailer header
    msg["X-Mailer"] = "TigerLeads.ai Email System"

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

    # Create plain text version for better deliverability (Gmail prefers multipart emails)
    plain_text_content = f"""You're Invited to Join a Team!

Hi there,

{inviter_name} has invited you to join their team on Tigerleads.ai

To Accept This Invitation:
- Login with this email: {recipient_email}
- Enter your password (or create one if you don't have an account yet)
- You will be redirected to {inviter_name}'s dashboard

Login Link: {login_link}

What Happens Next:
- Click the link above to go to the login page
- If you already have an account: Login with {recipient_email} and your password
- If you don't have an account: Click "Sign Up" and create one using {recipient_email}
- After logging in, you'll automatically be redirected to {inviter_name}'s dashboard
- You'll have access to shared leads and team resources

Important: You must use the email address {recipient_email} to accept this invitation. This email will be linked to {inviter_name}'s account.

Good news: This invitation never expires. You can accept it whenever you're ready!

Questions? Reply to this email or contact our support team.

Best regards,
The Tigerleads.ai Team

---
© {year} Tiger Leads.ai. All rights reserved.
    """

    # Attach both plain text and HTML content (Gmail prefers multipart emails)
    msg.attach(MIMEText(plain_text_content, "plain"))
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
        logger.info(f"SMTP User: {smtp_user}, From: {email_from}")

        # Optional debug BCC - set an env var `EMAIL_DEBUG_BCC` to receive copies for troubleshooting
        debug_bcc = os.getenv("EMAIL_DEBUG_BCC")
        recipients = [recipient_email]
        if debug_bcc:
            recipients.append(debug_bcc)
            msg["Bcc"] = debug_bcc

        logger.info(
            f"Sending team invitation email to {recipient_email} via {smtp_server}:{smtp_port} (recipients={recipients})"
        )

        if use_tls:
            async with aiosmtplib.SMTP(
                hostname=smtp_server, port=smtp_port, use_tls=True, timeout=30
            ) as server:
                if smtp_user and smtp_pass:
                    logger.info(f"Attempting SMTP login with user: {smtp_user}")
                    await server.login(smtp_user, smtp_pass)
                    logger.info("SMTP login successful")
                else:
                    logger.warning(
                        "No SMTP credentials provided - attempting unauthenticated send"
                    )

                logger.info(f"Sending message to recipients: {recipients}...")
                send_result = await server.send_message(msg, recipients=recipients)
                logger.info(
                    "Team invitation email sent successfully. SMTP response: %s, recipients: %s",
                    send_result,
                    recipients,
                )
                return True, None
        else:
            async with aiosmtplib.SMTP(
                hostname=smtp_server, port=smtp_port, start_tls=True, timeout=30
            ) as server:
                if smtp_user and smtp_pass:
                    await server.login(smtp_user, smtp_pass)
                send_result = await server.send_message(msg, recipients=recipients)
                logger.info(
                    "Team invitation email sent successfully to %s. SMTP response: %s",
                    recipients,
                    send_result,
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
    smtp_user = os.getenv("SMTP_USER")
    email_from = os.getenv("EMAIL_FROM") or smtp_user or "no-reply@tigerleads.com"
    msg["From"] = f"Tiger Leads.ai <{email_from}>"
    msg["To"] = recipient_email
    if smtp_user and smtp_user != email_from:
        msg["Sender"] = smtp_user
        logger.warning(
            "Email From (%s) differs from SMTP user (%s). Set up 'Send as' or use same address to improve deliverability.",
            email_from,
            smtp_user,
        )

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

        # Optional debug BCC - set an env var `EMAIL_DEBUG_BCC` to receive copies for troubleshooting
        debug_bcc = os.getenv("EMAIL_DEBUG_BCC")
        recipients = [recipient_email]
        if debug_bcc:
            recipients.append(debug_bcc)
            msg["Bcc"] = debug_bcc

        # Use implicit TLS (SMTPS) for port 465, otherwise use STARTTLS
        use_tls = smtp_port == 465

        logger.info(
            f"Sending password reset email to {recipient_email} via {smtp_server}:{smtp_port} (use_tls={use_tls}, recipients={recipients})"
        )

        if use_tls:
            async with aiosmtplib.SMTP(
                hostname=smtp_server, port=smtp_port, use_tls=True, timeout=30
            ) as server:
                if smtp_user and smtp_pass:
                    logger.info("Attempting SMTP login for password reset")
                    await server.login(smtp_user, smtp_pass)
                logger.info(
                    f"Sending password reset email to {recipient_email} (recipients={recipients})"
                )
                send_result = await server.send_message(msg, recipients=recipients)
                logger.info(
                    "Password reset email sent successfully to %s. SMTP response: %s",
                    recipients,
                    send_result,
                )
                return True, None
        else:
            async with aiosmtplib.SMTP(
                hostname=smtp_server, port=smtp_port, start_tls=True, timeout=30
            ) as server:
                if smtp_user and smtp_pass:
                    logger.info("Attempting SMTP login for password reset")
                    await server.login(smtp_user, smtp_pass)
                logger.info(
                    f"Sending password reset email to {recipient_email} (recipients={recipients})"
                )
                send_result = await server.send_message(msg, recipients=recipients)
                logger.info(
                    "Password reset email sent successfully to %s. SMTP response: %s",
                    recipients,
                    send_result,
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
