import logging
import os
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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
    """Send password reset link to user."""
    # Validate email
    is_valid, result = is_valid_email(recipient_email)
    if not is_valid:
        logger.error(f"Invalid email format: {recipient_email}")
        return False, "Please provide a valid email address format"

    sender_email = os.getenv("SMTP_USER", "ayeshashahid771771@gmail.com")
    sender_password = os.getenv("SMTP_PASSWORD", "jkee nsbx uvam ssez")

    subject = "TigerLeads Password Reset"
    body = (
        f"You requested a password reset. Click the link below to reset your password:\n\n"
        f"{reset_link}\n\n"
        "If you did not request this, you can ignore this email. The link will expire in 20 minutes."
    )

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        logger.info(f"Setting up SMTP connection for password reset to {recipient_email}")
        async with aiosmtplib.SMTP(hostname="smtp.gmail.com", port=465, use_tls=True) as server:
            await server.login(sender_email, sender_password)
            await server.send_message(msg)
            logger.info(f"Password reset email sent to {recipient_email}")
            return True, None
    except Exception as e:
        logger.error(f"Error sending password reset email to {recipient_email}: {str(e)}")
        return False, "Failed to send password reset email"