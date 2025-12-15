import asyncio
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM")

print("=" * 60)
print("EMAIL CONFIGURATION TEST")
print("=" * 60)
print(f"SMTP Server: {SMTP_SERVER}")
print(f"SMTP Port: {SMTP_PORT}")
print(f"SMTP User: {SMTP_USER}")
print(f"Email From: {EMAIL_FROM}")
print(f"Password: {'*' * len(SMTP_PASSWORD) if SMTP_PASSWORD else 'NOT SET'}")
print("=" * 60)


def test_sync_smtp():
    """Test synchronous SMTP connection and email sending."""
    print("\n[TEST 1] Testing Synchronous SMTP Connection...")

    try:
        # Test recipient email
        test_recipient = input("\nEnter recipient email address to test: ").strip()

        if not test_recipient:
            print("❌ No recipient email provided")
            return False

        # Create message
        msg = MIMEMultipart()
        msg["Subject"] = "Test Email - SMTP Connection Test"
        msg["From"] = EMAIL_FROM
        msg["To"] = test_recipient

        html_content = """
        <html>
        <body>
            <h2>SMTP Connection Test</h2>
            <p>This is a test email to verify SMTP connection is working.</p>
            <p>If you receive this, the email configuration is correct!</p>
            <hr>
            <p><small>Sent from Tiger Leads Backend</small></p>
        </body>
        </html>
        """

        msg.attach(MIMEText(html_content, "html"))

        print(f"\n🔄 Connecting to {SMTP_SERVER}:{SMTP_PORT}...")

        # Connect using SSL
        if SMTP_PORT == 465:
            print("   Using SSL connection...")
            server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=30)
        else:
            print("   Using TLS connection...")
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30)
            server.starttls()

        print("✓ Connection established")

        print(f"\n🔄 Logging in as {SMTP_USER}...")
        server.login(SMTP_USER, SMTP_PASSWORD)
        print("✓ Login successful")

        print(f"\n🔄 Sending email to {test_recipient}...")
        server.send_message(msg)
        print("✓ Email sent successfully")

        server.quit()
        print("\n✅ SYNCHRONOUS SMTP TEST PASSED")
        return True

    except smtplib.SMTPAuthenticationError as e:
        print(f"\n❌ AUTHENTICATION FAILED: {e}")
        print("\nPossible issues:")
        print("  - Incorrect username or password")
        print("  - App password not generated (for Gmail)")
        print("  - 2-Step Verification not enabled")
        return False

    except smtplib.SMTPException as e:
        print(f"\n❌ SMTP ERROR: {e}")
        return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


async def test_async_smtp():
    """Test asynchronous SMTP connection and email sending (like the actual code)."""
    print("\n[TEST 2] Testing Asynchronous SMTP Connection...")

    try:
        test_recipient = input("\nEnter recipient email address to test: ").strip()

        if not test_recipient:
            print("❌ No recipient email provided")
            return False

        # Create message
        msg = MIMEMultipart()
        msg["Subject"] = "Test Email - Async SMTP Connection Test"
        msg["From"] = EMAIL_FROM
        msg["To"] = test_recipient

        html_content = """
        <html>
        <body>
            <h2>Async SMTP Connection Test</h2>
            <p>This is a test email using async SMTP (same as production code).</p>
            <p>If you receive this, the async email configuration is correct!</p>
            <hr>
            <p><small>Sent from Tiger Leads Backend (Async)</small></p>
        </body>
        </html>
        """

        msg.attach(MIMEText(html_content, "html"))

        print(f"\n🔄 Connecting to {SMTP_SERVER}:{SMTP_PORT} (async)...")

        # Use aiosmtplib (same as production)
        smtp_client = aiosmtplib.SMTP(
            hostname=SMTP_SERVER, port=SMTP_PORT, use_tls=True, timeout=30
        )

        await smtp_client.connect()
        print("✓ Async connection established")

        print(f"\n🔄 Logging in as {SMTP_USER} (async)...")
        await smtp_client.login(SMTP_USER, SMTP_PASSWORD)
        print("✓ Async login successful")

        print(f"\n🔄 Sending email to {test_recipient} (async)...")
        await smtp_client.send_message(msg)
        print("✓ Async email sent successfully")

        await smtp_client.quit()
        print("\n✅ ASYNCHRONOUS SMTP TEST PASSED")
        return True

    except aiosmtplib.SMTPAuthenticationError as e:
        print(f"\n❌ ASYNC AUTHENTICATION FAILED: {e}")
        print("\nPossible issues:")
        print("  - Incorrect username or password")
        print("  - App password not generated (for Gmail)")
        print("  - 2-Step Verification not enabled")
        return False

    except Exception as e:
        print(f"\n❌ ASYNC ERROR: {e}")
        return False


def check_gmail_account():
    """Check if Gmail account is accessible and provide guidance."""
    print("\n[INFO] Gmail Account Checklist:")
    print("=" * 60)
    print("For Gmail SMTP to work, ensure:")
    print("  1. 2-Step Verification is ENABLED on the account")
    print("  2. App Password is generated (not regular password)")
    print("  3. Account is not locked or suspended")
    print("  4. Less secure app access is NOT required (use App Password)")
    print("\nTo generate App Password:")
    print("  1. Go to: https://myaccount.google.com/security  ")
    print("  2. Enable 2-Step Verification (if not enabled)")
    print("  3. Go to 'App passwords'")
    print("  4. Generate password for 'Mail' app")
    print("  5. Copy the 16-character password (no spaces)")
    print("  6. Update .env file with new password")
    print("=" * 60)


async def main():
    """Run all tests."""
    print("\n🚀 Starting Email Connection Tests...\n")

    if not SMTP_USER or not SMTP_PASSWORD:
        print("❌ ERROR: SMTP_USER or SMTP_PASSWORD not set in .env file")
        return

    # Show Gmail checklist
    check_gmail_account()

    input("\nPress Enter to continue with tests...")

    # Test 1: Synchronous SMTP
    sync_result = test_sync_smtp()

    if not sync_result:
        print("\n⚠️  Synchronous test failed. Skipping async test.")
        print("\nPlease fix the SMTP configuration and try again.")
        return

    # Test 2: Asynchronous SMTP
    print("\n" + "=" * 60)
    async_result = await test_async_smtp()

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Synchronous SMTP: {'✅ PASSED' if sync_result else '❌ FAILED'}")
    print(f"Asynchronous SMTP: {'✅ PASSED' if async_result else '❌ FAILED'}")
    print("=" * 60)

    if sync_result and async_result:
        print("\n🎉 All tests passed! Email configuration is working correctly.")
        print("If emails still don't arrive, check:")
        print("  - Spam/Junk folders")
        print("  - Gmail 'Sent' folder on the sender account")
        print("  - Recipient email blocks or filters")
    else:
        print("\n❌ Some tests failed. Please fix the issues above.")


if __name__ == "__main__":
    asyncio.run(main())
