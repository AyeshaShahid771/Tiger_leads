"""
Check and optionally disable 2FA for a user.

This script helps diagnose and fix the "No token returned from backend" error
that occurs when a user has 2FA enabled but the frontend doesn't support it.
"""

import sys
from sqlalchemy.orm import Session
from src.app.database import SessionLocal
from src.app.models.user import User


def check_user_2fa(email: str):
    """Check if user has 2FA enabled."""
    db = SessionLocal()
    
    try:
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            print(f"❌ User not found: {email}")
            return None
        
        print(f"\n📧 User: {email}")
        print(f"🔐 2FA Enabled: {user.two_factor_enabled}")
        
        if user.two_factor_secret:
            print(f"🔑 2FA Secret: {user.two_factor_secret[:10]}...")
        else:
            print(f"🔑 2FA Secret: None")
        
        if user.two_factor_enabled_at:
            print(f"📅 2FA Enabled At: {user.two_factor_enabled_at}")
        else:
            print(f"📅 2FA Enabled At: Never")
        
        return user
    
    finally:
        db.close()


def disable_user_2fa(email: str):
    """Disable 2FA for a user."""
    db = SessionLocal()
    
    try:
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            print(f"❌ User not found: {email}")
            return False
        
        if not user.two_factor_enabled:
            print(f"ℹ️  2FA is already disabled for {email}")
            return True
        
        # Disable 2FA
        user.two_factor_enabled = False
        user.two_factor_secret = None
        user.two_factor_enabled_at = None
        
        db.commit()
        
        print(f"\n✅ 2FA disabled successfully for {email}")
        print(f"✅ User can now login with just email + password")
        print(f"✅ Will receive access_token immediately")
        
        return True
    
    except Exception as e:
        db.rollback()
        print(f"❌ Error disabling 2FA: {str(e)}")
        return False
    
    finally:
        db.close()


def main():
    print("=" * 60)
    print("2FA Status Checker and Disabler")
    print("=" * 60)
    
    # Default email (the one having issues)
    default_email = "ayeshashahid77177@gmail.com"
    
    # Get email from command line or use default
    if len(sys.argv) > 1:
        email = sys.argv[1]
    else:
        email = default_email
    
    # Check current status
    print(f"\n🔍 Checking 2FA status for: {email}\n")
    user = check_user_2fa(email)
    
    if not user:
        return
    
    # If 2FA is enabled, ask if user wants to disable it
    if user.two_factor_enabled:
        print(f"\n⚠️  This user has 2FA enabled!")
        print(f"⚠️  This is why login returns 'temp_token' instead of 'access_token'")
        print(f"⚠️  Frontend shows: 'No token returned from backend'\n")
        
        # Auto-disable if running with --disable flag
        if len(sys.argv) > 2 and sys.argv[2] == "--disable":
            print(f"🔧 Auto-disabling 2FA...")
            disable_user_2fa(email)
        else:
            response = input(f"Do you want to disable 2FA for this user? (yes/no): ")
            
            if response.lower() in ['yes', 'y']:
                disable_user_2fa(email)
            else:
                print(f"\n✋ 2FA not disabled")
                print(f"\nℹ️  To fix the login issue, you need to either:")
                print(f"   1. Disable 2FA (run this script again and choose 'yes')")
                print(f"   2. Update frontend to handle 2FA flow")
                print(f"   3. See: 2fa_login_flow.md for details")
    else:
        print(f"\n✅ 2FA is NOT enabled for this user")
        print(f"✅ Login should work normally")
        print(f"\nℹ️  If still getting 'No token returned', check:")
        print(f"   1. Password is correct")
        print(f"   2. Email is verified")
        print(f"   3. User has a role set (Contractor/Supplier)")
        print(f"   4. Check server logs for errors")


if __name__ == "__main__":
    main()
