"""
Update contractor user_id 10 with specific user_type, state, and country_city values
"""
import os
import sys
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Load environment variables from .env file
load_dotenv()

# Database connection (same as database.py)
password = quote_plus("Xb@qeJk3")  # URL encode the password
_raw_db = os.getenv(
    "DATABASE_URL", f"postgresql://postgres:{password}@localhost:5432/Tiger_leads"
)

# Tolerate misconfigured environment values
if isinstance(_raw_db, str):
    if _raw_db.startswith("DATABASE_URL="):
        _raw_db = _raw_db.split("=", 1)[1]
    if (_raw_db.startswith('"') and _raw_db.endswith('"')) or (
        _raw_db.startswith("'") and _raw_db.endswith("'")
    ):
        _raw_db = _raw_db[1:-1]

DATABASE_URL = _raw_db

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def update_contractor_10():
    """Update contractor with user_id=10"""
    db = SessionLocal()
    
    try:
        # New values
        user_type = [
            "erosion_materials",
            "erosion_control_contractor",
            "land_clearing_contractor",
            "electrical_contractor",
            "low_voltage_contractor"
        ]
        state = ["Florida"]
        country_city = ["Florida"]
        
        # Update the contractor
        result = db.execute(
            text("""
                UPDATE contractors 
                SET 
                    user_type = :user_type,
                    state = :state,
                    country_city = :country_city
                WHERE user_id = 10
                RETURNING user_id, user_type, state, country_city
            """),
            {
                "user_type": user_type,
                "state": state,
                "country_city": country_city
            }
        )
        
        db.commit()
        
        updated = result.fetchone()
        if updated:
            print("✅ Contractor updated successfully!")
            print(f"   User ID: {updated[0]}")
            print(f"   User Type: {updated[1]}")
            print(f"   State: {updated[2]}")
            print(f"   Country/City: {updated[3]}")
        else:
            print("❌ No contractor found with user_id=10")
            
    except Exception as e:
        db.rollback()
        print(f"❌ Error updating contractor: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    print("Updating contractor with user_id=10...")
    update_contractor_10()
