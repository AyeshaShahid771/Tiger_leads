"""
Script to delete a user by email from the users table.
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def delete_user_by_email(email: str):
    """Delete a user by email address."""
    
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        try:
            print(f"Searching for user with email: {email}")
            
            # Check if user exists
            result = conn.execute(
                text("SELECT id, email, role FROM users WHERE email = :email"),
                {"email": email}
            )
            user = result.fetchone()
            
            if not user:
                print(f"❌ No user found with email: {email}")
                return
            
            user_id, user_email, user_role = user
            print(f"\nFound user:")
            print(f"  ID: {user_id}")
            print(f"  Email: {user_email}")
            print(f"  Role: {user_role}")
            
            # Delete the user
            print(f"\nDeleting user...")
            conn.execute(
                text("DELETE FROM users WHERE email = :email"),
                {"email": email}
            )
            
            conn.commit()
            
            print(f"\n✅ Successfully deleted user with email: {email}")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            conn.rollback()
            raise

if __name__ == "__main__":
    # Email to delete
    email_to_delete = "foryoutuba25@gmail.com"
    delete_user_by_email(email_to_delete)
