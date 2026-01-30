"""
Get email for user ID 91
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Load environment variables
load_dotenv()

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment variables")
    exit(1)

# Create database connection
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

try:
    # Query user with ID 91
    result = db.execute(
        text("SELECT id, email, role, two_factor_enabled FROM users WHERE id = :user_id"),
        {"user_id": 91}
    )
    user = result.fetchone()
    
    if user:
        print(f"\n✅ User Found!")
        print(f"ID: {user[0]}")
        print(f"Email: {user[1]}")
        print(f"Role: {user[2]}")
        print(f"2FA Enabled: {user[3]}")
    else:
        print(f"\n❌ No user found with ID 91")
        
except Exception as e:
    print(f"\n❌ Error: {str(e)}")
finally:
    db.close()
