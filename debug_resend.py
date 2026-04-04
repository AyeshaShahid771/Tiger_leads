#!/usr/bin/env python
"""
Resend API Debug Script
Tests if Resend API is working, validates API key, and sends test email
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

# Load .env file
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path)
    print(f"Loaded .env from: {env_path}")
except ImportError:
    print("Note: python-dotenv not found, loading env manually")
    # Manual .env loading
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()

print("\n" + "=" * 80)
print("RESEND API DEBUG SCRIPT")
print("=" * 80 + "\n")

# Check environment
print("Step 1: Checking environment variables...")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
FRONTEND_URL = os.environ.get("FRONTEND_URL")

if RESEND_API_KEY:
    print(f"✓ RESEND_API_KEY found: {RESEND_API_KEY[:20]}...***")
else:
    print("✗ RESEND_API_KEY not found!")

if FRONTEND_URL:
    print(f"✓ FRONTEND_URL: {FRONTEND_URL}")
else:
    print("✗ FRONTEND_URL not set")

# Try importing Resend
print("\nStep 2: Checking Resend SDK...")
try:
    import resend

    print(f"✓ Resend SDK imported successfully")
    print(f"  Resend version: {getattr(resend, '__version__', 'unknown')}")
except ImportError as e:
    print(f"✗ Failed to import Resend: {e}")
    sys.exit(1)

# Set API key
print("\nStep 3: Setting Resend API key...")
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY
    print(f"✓ API key set")
else:
    print("✗ Cannot set API key - not found in environment")
    sys.exit(1)

# Test 1: Simple email send
print("\nStep 4: Sending test email via Resend API...")
test_email = "test@example.com"  # Change to your test email
subject = "Tiger Leads - Test OTP Email"
html = """
<html>
<body>
    <h2>Test Email from Tiger Leads</h2>
    <p>If you're receiving this, Resend API is working!</p>
    <div style="background:#f8f9fa; border:2px dashed #f58220; padding:20px; margin:20px 0;">
        <p style="color:#666; margin:5px 0;">Your Test Code:</p>
        <p style="font-size:32px; font-weight:bold; color:#f58220; margin:10px 0; font-family:'Courier New';">123456</p>
    </div>
    <p>This code will expire in 10 minutes.</p>
    <hr>
    <p style="color:#999; font-size:12px;">If you did not request this, please ignore this email.</p>
</body>
</html>
"""

try:
    print(f"  Sending test email to: {test_email}")
    print(f"  From: Accounts@tigerleads.ai")
    print(f"  Subject: {subject}")

    response = resend.Emails.send(
        {
            "from": "Accounts@tigerleads.ai",
            "to": [test_email],
            "subject": subject,
            "html": html,
        }
    )

    print(f"\n✓ EMAIL SENT SUCCESSFULLY!")
    print(f"  Response: {response}")

    if hasattr(response, "id"):
        print(f"  Email ID: {response.id}")
    if hasattr(response, "from_addr"):
        print(f"  From: {response.from_addr}")

except Exception as e:
    print(f"\n✗ FAILED TO SEND EMAIL")
    print(f"  Error type: {type(e).__name__}")
    print(f"  Error message: {str(e)}")
    print(f"\n  Full error details:")
    import traceback

    traceback.print_exc()

# Test 2: Check if domain is verified
print("\n\nStep 5: Checking Resend domain verification...")
try:
    domains = resend.Domains.list()
    print(f"✓ Retrieved domains from Resend:")

    if hasattr(domains, "data") and domains.data:
        for domain in domains.data:
            print(f"\n  Domain: {domain.get('domain', 'N/A')}")
            print(f"    Status: {domain.get('status', 'N/A')}")
            print(f"    Created: {domain.get('created_at', 'N/A')}")
    else:
        print(f"  No domains found or unexpected response format")
        print(f"  Response: {domains}")

except Exception as e:
    print(f"✗ Failed to retrieve domains")
    print(f"  Error: {str(e)}")

# Test 3: Check API key validity
print("\n\nStep 6: Validating API key...")
try:
    # Try a simple API call to validate key
    test_response = resend.Emails.send(
        {
            "from": "Accounts@tigerleads.ai",
            "to": ["invalid-test-to-validate-key@example.com"],
            "subject": "Key Validation Test",
            "html": "<p>Test</p>",
        }
    )
    print(f"✓ API key appears to be VALID")
    print(f"  Response: {test_response}")

except Exception as e:
    error_str = str(e).lower()
    if "unauthorized" in error_str or "invalid" in error_str or "403" in error_str:
        print(f"✗ API KEY IS INVALID or EXPIRED")
        print(f"  Please check your RESEND_API_KEY in .env")
    elif "domain" in error_str or "not verified" in error_str:
        print(f"✗ DOMAIN NOT VERIFIED in Resend")
        print(f"  Verify 'tigerleads.ai' domain in Resend dashboard")
    else:
        print(f"⚠ Unexpected error: {str(e)}")

print("\n" + "=" * 80)
print("DEBUG COMPLETE")
print("=" * 80 + "\n")

print("NEXT STEPS:")
print("1. If email was sent but not received:")
print("   - Check spam/junk folder")
print("   - Check Resend dashboard for delivery status")
print("   - Verify domain is confirmed in Resend")
print("   - Check if you have free credits/plan in Resend\n")

print("2. If API key is invalid:")
print("   - Get new key from Resend dashboard")
print("   - Update RESEND_API_KEY in .env")
print("   - Restart backend server\n")

print("3. If domain not verified:")
print("   - Log into Resend.com")
print("   - Go to Domains")
print("   - Add/verify 'tigerleads.ai' domain")
print("   - Add DNS records as shown\n")

print("4. To test with real signup:")
print("   - Use this test email: your-test-email@gmail.com")
print("   - Sign up and check inbox + spam folder")
print("   - If still no email, share the error from backend logs\n")
