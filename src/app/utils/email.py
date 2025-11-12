import logging
import os
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

import aiosmtplib
from dotenv import load_dotenv
from email_validator import EmailNotValidError, validate_email

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

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
    # First validate email format
    is_valid, result = is_valid_email(recipient_email)
    if not is_valid:
        logger.error(f"Invalid email format: {recipient_email}")
        return False, "Please provide a valid email address format"

    sender_email = os.getenv("SMTP_USER", "ayeshashahid771771@gmail.com")
    sender_password = os.getenv("SMTP_PASSWORD", "jkee nsbx uvam ssez")

    subject = "TigerLeads Email Verification Code"
    body = f"Your verification code is: {code}\nThis code will expire in 10 minutes."

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        logger.info(f"Setting up SMTP connection for {recipient_email}")
        logger.info(f"Using sender email: {sender_email}")
        
        async with aiosmtplib.SMTP(hostname="smtp.gmail.com", port=465, use_tls=True) as server:
            logger.info("Attempting SMTP login")
            await server.login(sender_email, sender_password)
            
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


async def send_password_reset_email(recipient_email: str, reset_link: str):
        """Send password reset email with inline (CID) logo image using async SMTP.

        Uses `app/static/logo.png` as the embedded image. Returns (True, None) or (False, error).
        """
        # Validate email
        is_valid, result = is_valid_email(recipient_email)
        if not is_valid:
                logger.error(f"Invalid email format: {recipient_email}")
                return False, "Please provide a valid email address format"

        subject = "Reset Your Password – Tiger Leads"
        year = datetime.utcnow().year

        # Path to your local logo (relative to project root)
        logo_path = os.getenv("RESET_EMAIL_LOGO_PATH", "app/static/logo.png")

        # Create multipart/related message for inline image
        msg = MIMEMultipart("related")
        msg["Subject"] = subject
        msg["From"] = os.getenv("EMAIL_FROM", os.getenv("SMTP_USER", "no-reply@tigerleads.com"))
        msg["To"] = recipient_email

        # HTML content referencing the CID image
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: 'Segoe UI', Roboto, Arial, sans-serif; background-color: #f9f9fb; color: #333; margin: 0; padding: 0;">
            <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); overflow: hidden;">
                <!-- Header with embedded Logo -->
                <div style="background-color: #ffffff; text-align: center; padding: 25px 0; border-bottom: 1px solid #eee;">
                    <img src="cid:logo_image" alt="Tiger Leads" style="width: 160px; height: auto;" />
                </div>

                <div style="padding: 30px;">
                    <h2 style="color: #222;">Password Reset Request</h2>
                    <p style="line-height: 1.6;">
                        Hello,<br><br>
                        We received a request to reset your password for your <strong>Tiger Leads</strong> account.
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
                        If you didn’t request a password reset, you can safely ignore this email.
                    </p>

                    <p>Best regards,<br><strong>The Tiger Leads Team</strong></p>
                </div>

                <div style="background-color: #fafafa; text-align: center; padding: 15px; font-size: 12px; color: #777; border-top: 1px solid #eee;">
                    &copy; {year} Tiger Leads. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """

        # Attach the HTML part as alternative
        alternative = MIMEMultipart("alternative")
        alternative.attach(MIMEText(html_content, "html"))
        msg.attach(alternative)

        # Attach inline image
        try:
                with open(logo_path, "rb") as img_file:
                        img = MIMEImage(img_file.read())
                        img.add_header("Content-ID", "<logo_image>")
                        img.add_header("Content-Disposition", "inline", filename=os.path.basename(logo_path))
                        msg.attach(img)
        except FileNotFoundError:
                logger.warning(f"Logo file not found at {logo_path}; sending email without inline image")
        except Exception as e:
                logger.error(f"Error attaching logo image: {str(e)}")

        # Send via aiosmtplib
        try:
                smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
                smtp_port = int(os.getenv("SMTP_PORT", 587))
                smtp_user = os.getenv("SMTP_USER")
                smtp_pass = os.getenv("SMTP_PASSWORD")

                logger.info(f"Sending password reset email to {recipient_email} via {smtp_server}:{smtp_port}")

                async with aiosmtplib.SMTP(hostname=smtp_server, port=smtp_port, start_tls=True) as server:
                        if smtp_user and smtp_pass:
                                await server.login(smtp_user, smtp_pass)
                        await server.send_message(msg)
                        logger.info(f"Password reset email sent to {recipient_email}")
                        return True, None
        except Exception as e:
                logger.error(f"Error sending password reset email to {recipient_email}: {str(e)}")
                return False, str(e)