import base64
import logging
import os
import re
from datetime import datetime
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import resend
from dotenv import find_dotenv, load_dotenv
from email_validator import EmailNotValidError, validate_email

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env reliably (works when cwd differs from project root)
dotenv_path = find_dotenv()
if dotenv_path:
    load_dotenv(dotenv_path)
else:
    # Fall back to default behaviour
    load_dotenv()

# Define logo path
LOGO_PATH = Path.cwd() / "src" / "public" / "logo.png"


def is_valid_email(email: str) -> tuple[bool, str]:
    try:
        # First try a full deliverability check (may perform DNS/SMTP lookups)
        validation = validate_email(email, check_deliverability=True)
        normalized_email = validation.email
        return True, normalized_email
    except EmailNotValidError as e:
        # Syntactic validation failed
        return False, str(e)
    except Exception as e:
        # Deliverability check may fail in constrained environments (no DNS access).
        # Fall back to syntax-only validation to avoid blocking email sends.
        logger.warning(
            f"Deliverability check failed for {email}: {e}. Falling back to syntax-only validation."
        )
        try:
            validation = validate_email(email, check_deliverability=False)
            normalized_email = validation.email
            return True, normalized_email
        except EmailNotValidError as se:
            return False, str(se)
        except Exception as se:
            logger.error(f"Syntax-only email validation also failed for {email}: {se}")
            return False, "Email validation failed, please try again"


async def send_verification_email(recipient_email: str, code: str):
    """Send verification code email using Resend API. Returns (True, None) or (False, error)."""
    logger.info(f"[Resend] Preparing to send verification email to: {recipient_email}")
    is_valid, result = is_valid_email(recipient_email)
    if not is_valid:
        logger.error(f"[Resend] Invalid email format: {recipient_email} ({result})")
        return False, "Please provide a valid email address format"

    subject = "Verify Your Email – Tiger Leads.ai"
    year = datetime.utcnow().year

    # Use a consistent styled HTML header and avoid embedding logo images
    logo_html = '<h1 style="color: #f58220; margin: 0; font-size: 28px; font-weight: 800;">Tiger Leads ai</h1>'

    html_content = f"""
        <!DOCTYPE html>
        <html>
        <body style='font-family: "Segoe UI", Roboto, Arial, sans-serif; background-color: #f9f9fb; color: #333; margin: 0; padding: 0;'>
            <div style='max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); overflow: hidden;'>
                <div style='background-color: #ffffff; text-align: center; padding: 25px 0; border-bottom: 1px solid #eee;'>
                    {logo_html}
                </div>
                <div style='padding: 30px;'>
                    <h2 style='color: #222;'>Welcome to Tiger Leads.ai!</h2>
                    <p style='line-height: 1.6;'>Thank you for signing up. To complete your registration and verify your email address, please use the verification code below:</p>
                    <div style='text-align: center; margin: 30px 0;'>
                        <div style='background-color: #f8f9fa; border: 2px dashed #f58220; border-radius: 8px; padding: 20px; display: inline-block;'>
                            <p style='margin: 0; font-size: 14px; color: #666; font-weight: 500;'>Your Verification Code</p>
                            <p style='margin: 10px 0 0 0; font-size: 32px; font-weight: bold; color: #f58220; letter-spacing: 4px; font-family: "Courier New", monospace;'>{code}</p>
                        </div>
                    </div>
                    <p style='color: #d35400; font-weight: bold; text-align: center;'>⏱️ This code will expire in 10 minutes</p>
                    <p style='margin-top: 30px; line-height: 1.6;'>Enter this code on the verification page to activate your account and start using Tiger Leads.ai.</p>
                    <p style='margin-top: 30px;'>Best regards,<br><strong>The Tiger Leads.ai Team</strong></p>
                </div>
                <div style='background-color: #fafafa; text-align: center; padding: 15px; font-size: 12px; color: #777; border-top: 1px solid #eee;'>
                    &copy; {year} Tiger Leads. All rights reserved.
                </div>
            </div>
        </body>
        </html>
    """

    # Require Resend API key and send via Resend only
    resend_key = os.environ.get("RESEND_API_KEY")
    if not resend_key:
        logger.error("RESEND_API_KEY not configured; cannot send verification email")
        return False, "Email service not configured"

    try:
        resend.api_key = resend_key
        # Also provide a plain-text fallback to improve deliverability and avoid clipping
        plain_text = (
            f"Welcome to Tiger Leads.ai!\n\n"
            f"Thank you for signing up. Use the verification code: {code}\n\n"
            f"This code will expire in 10 minutes.\n\n"
            f"If you didn't request this, ignore this email.\n\n"
            f"© {year} Tiger Leads.ai"
        )
        params = {
            "from": "Accounts@tigerleads.ai",
            "to": [recipient_email],
            "subject": subject,
            "html": html_content,
            "text": plain_text,
        }
        logger.info(
            f"[Resend] Sending verification email to {recipient_email} via Resend API..."
        )
        response = resend.Emails.send(params)
        logger.info(
            f"[Resend] Email sent to {recipient_email}. Resend response: {response}"
        )
        return True, None
    except Exception as e:
        logger.error(
            f"[Resend] Failed to send verification email to {recipient_email}: {e}"
        )
        return False, f"Failed to send verification email: {e}"
        subject = "Verify Your Email – Tiger Leads.ai"
        year = datetime.utcnow().year
        # ... (logo logic and html_content as above)
        html_content = f"""
            <!DOCTYPE html>
            <html>
            <body style=\"font-family: 'Segoe UI', Roboto, Arial, sans-serif; background-color: #f9f9fb; color: #333; margin: 0; padding: 0;\">
                <div style=\"max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); overflow: hidden;\">
                    <!-- Header with embedded Logo -->
                    <div style=\"background-color: #ffffff; text-align: center; padding: 25px 0; border-bottom: 1px solid #eee;\">
                        Tiger Leads
                    </div>
                    <div style=\"padding: 30px;\">
                        <h2 style=\"color: #222;\">Welcome to Tiger Leads.ai!</h2>
                        <p style=\"line-height: 1.6;\">
                            Thank you for signing up. To complete your registration and verify your email address, please use the verification code below:
                        </p>
                        <div style=\"text-align: center; margin: 30px 0;\">
                            <div style=\"background-color: #f8f9fa; border: 2px dashed #f58220; border-radius: 8px; padding: 20px; display: inline-block;\">
                                <p style=\"margin: 0; font-size: 14px; color: #666; font-weight: 500;\">Your Verification Code</p>
                                <p style=\"margin: 10px 0 0 0; font-size: 32px; font-weight: bold; color: #f58220; letter-spacing: 4px; font-family: 'Courier New', monospace;\">{code}</p>
                            </div>
                        </div>
                        <p style=\"color: #d35400; font-weight: bold; text-align: center;\">⏱️ This code will expire in 10 minutes</p>
                        <p style=\"margin-top: 30px; line-height: 1.6;\">
                            Enter this code on the verification page to activate your account and start using Tiger Leads.ai.
                        </p>
                        <p style=\"margin-top: 30px;\">Best regards,<br><strong>The Tiger Leads.ai Team</strong></p>
                    </div>
                    <div style=\"background-color: #fafafa; text-align: center; padding: 15px; font-size: 12px; color: #777; border-top: 1px solid #eee;\">
                        &copy; {year} Tiger Leads. All rights reserved.
                    </div>
                </div>
            </body>
            </html>
            """
        resend.api_key = os.environ["RESEND_API_KEY"]
        params = {
            "from": "Accounts@tigerleads.ai",
            "to": [recipient_email],
            "subject": subject,
            "html": html_content,
        }
        return resend.Emails.send(params)


async def send_team_invitation_email(
    recipient_email: str,
    inviter_name: str,
    invitation_token: str,
    frontend_url: str,
    set_password_link: str | None = None,
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
    # Include invitation token in login link so frontend can exchange it for an access token
    login_link = f"{frontend_url}/login?invite_token={invitation_token}"

    # Avoid embedding logo images; use styled text header instead

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

    # Use styled header (no images)
    logo_html = '<h1 style="color: #f58220; margin: 0; font-size: 28px; font-weight: 800;">Tiger Leads ai</h1>'

    html_content = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: 'Segoe UI', Roboto, Arial, sans-serif; background-color: #ffffff; color: #111; margin: 0; padding: 0;">
            <div style="max-width: 600px; margin: 28px auto; padding: 24px; border-radius:8px;">
                {logo_html}
                <p style="font-size:16px; color:#222; margin-top:18px; margin-bottom:6px;">{inviter_name} invited you to join their team on Tiger Leads ai.</p>
                <p style="font-size:15px; color:#333; margin-top:0;">To accept, <a href="{login_link}" style="color:#f58220; font-weight:700; text-decoration:none;">log in</a> using this email: <strong style="color:#f58220;">{recipient_email}</strong>.</p>
                <div style="text-align:left; margin-top:18px;">
                    <p style="font-size:14px; color:#444; margin:0;">After you log in, you'll be taken to <strong style="color:#222;">{inviter_name}'s dashboard</strong> and given access to shared leads.</p>
                </div>
                <div style="text-align:center; margin-top:22px;">
                    <a href="{login_link}" style="background:#f58220;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:700;display:inline-block;">Log in to accept</a>
                </div>
                {f"<div style=\"text-align:center; margin-top:14px;\"><a href=\"{set_password_link}\" style=\"display:inline-block;padding:8px 16px;border-radius:6px;background:#fff;color:#f58220;border:1px solid #f58220;text-decoration:none;font-weight:700;\">Set your password</a></div>" if set_password_link else ""}
                <p style="font-size:13px; color:#999; margin-top:22px;">© {year} Tiger Leads.ai</p>
            </div>
        </body>
        </html>
    """

    # Send via Resend only (no SMTP fallback)
    resend_key = os.environ.get("RESEND_API_KEY")
    if not resend_key:
        logger.error("RESEND_API_KEY not configured; cannot send team invitation email")
        return False, "Email service not configured"

    try:
        resend.api_key = resend_key
        # Plain-text fallback for clients that do not render HTML
        plain_text_content = (
            f"{inviter_name} invited you to join their team on Tiger Leads ai.\n\n"
            f"To accept, log in: {login_link}\n\n"
            f"Use this email to log in: {recipient_email}\n\n"
            f"After logging in you'll be taken to {inviter_name}'s dashboard and given access to shared leads.\n\n"
            f"Set your password: {set_password_link}\n\n" if set_password_link
            else ""
            + "— Tiger Leads.ai"
        )

        params = {
            "from": "Accounts@tigerleads.ai",
            "to": [recipient_email],
            "subject": subject,
            "html": html_content,
            "text": plain_text_content,
        }
        logger.info(
            f"[Resend] Sending team invitation email to {recipient_email} via Resend API..."
        )
        resp = resend.Emails.send(params)
        logger.info(
            f"[Resend] Team invitation email sent to {recipient_email}. Resend response: {resp}"
        )
        return True, None
    except Exception as e:
        logger.error(f"[Resend] Failed to send team invitation via Resend: {e}")
        return False, f"Failed to send invitation email: {e}"


async def send_password_reset_email(recipient_email: str, reset_link: str):
    """Send password reset email with inline (CID) logo image using async SMTP.

    Uses `app/static/logo.png` as the embedded image. Returns (True, None) or (False, error).
    """
    logger.info(f"Preparing password reset email to: {recipient_email}")

    # Validate email
    is_valid, result = is_valid_email(recipient_email)
    if not is_valid:
        logger.error(f"Invalid email format: {recipient_email}")
        return False, "Please provide a valid email address format"

    subject = "Reset Your Password – Tiger Leads.ai"
    year = datetime.utcnow().year

    # Avoid embedding logo images; use styled text header instead

    # Create message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject

    smtp_user = os.getenv("SMTP_USER")
    email_from = os.getenv("EMAIL_FROM") or smtp_user or "no-reply@tigerleads.com"

    if not smtp_user or email_from == smtp_user:
        msg["From"] = f"Tiger Leads.ai <{email_from}>"
    else:
        # Match test script: authenticated user as From, configured EMAIL_FROM as Reply-To
        msg["From"] = f"Tiger Leads.ai <{smtp_user}>"
        msg["Reply-To"] = email_from
        logger.info(
            "Password reset email: using SMTP user (%s) as From, EMAIL_FROM=%s as Reply-To",
            smtp_user,
            email_from,
        )

    msg["To"] = recipient_email

    # Use styled header (no images)
    logo_html = '<h1 style="color: #f58220; margin: 0; font-size: 28px; font-weight: 800;">Tiger Leads ai</h1>'

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

    # Create a plain-text fallback and attach both plain text and HTML
    plain_text_reset = (
        "Password Reset Request\n\n"
        "We received a request to reset your password for your Tiger Leads.ai account.\n\n"
        f"Reset link: {reset_link}\n\n"
        "This link will expire in 20 minutes.\n\n"
        "If you didn't request a password reset, you can safely ignore this email.\n\n"
        f"© {year} Tiger Leads.ai. All rights reserved."
    )
    msg.attach(MIMEText(plain_text_reset, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    # Send via Resend only (no SMTP fallback)
    resend_key = os.environ.get("RESEND_API_KEY")
    if not resend_key:
        logger.error("RESEND_API_KEY not configured; cannot send password reset email")
        return False, "Email service not configured"

    try:
        resend.api_key = resend_key
        params = {
            "from": "Accounts@tigerleads.ai",
            "to": [recipient_email],
            "subject": subject,
            "html": html_content,
            "text": plain_text_reset,
        }
        logger.info(
            f"[Resend] Sending password reset email to {recipient_email} via Resend API..."
        )
        resp = resend.Emails.send(params)
        logger.info(
            f"[Resend] Password reset email sent to {recipient_email}. Resend response: {resp}"
        )
        return True, None
    except Exception as e:
        logger.error(f"[Resend] Failed to send password reset email via Resend: {e}")
        return False, f"Failed to send password reset email: {e}"

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

        send_start = datetime.utcnow()

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
                send_end = datetime.utcnow()
                duration_ms = int((send_end - send_start).total_seconds() * 1000)
                logger.info(
                    "Password reset email sent successfully to %s. SMTP response: %s; duration_ms=%s",
                    recipients,
                    send_result,
                    duration_ms,
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
                send_end = datetime.utcnow()
                duration_ms = int((send_end - send_start).total_seconds() * 1000)
                logger.info(
                    "Password reset email sent successfully to %s. SMTP response: %s; duration_ms=%s",
                    recipients,
                    send_result,
                    duration_ms,
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
