"""
Fix user_invitations sequence issue.
The sequence is out of sync with the actual data.
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def fix_invitation_sequence():
    """Reset the user_invitations_id_seq to the correct value."""
    
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        try:
            # Get the current max ID
            result = conn.execute(text("SELECT MAX(id) FROM user_invitations;"))
            max_id = result.scalar()
            
            if max_id is None:
                max_id = 0
            
            print(f"Current max ID in user_invitations: {max_id}")
            
            # Reset the sequence to max_id + 1
            conn.execute(text(f"SELECT setval('user_invitations_id_seq', {max_id + 1}, false);"))
            
            print(f"✓ Reset sequence to {max_id + 1}")
            
            # Verify the sequence
            result = conn.execute(text("SELECT last_value FROM user_invitations_id_seq;"))
            last_value = result.scalar()
            print(f"✓ Sequence last_value is now: {last_value}")
            
            conn.commit()
            print("\n✅ Successfully fixed user_invitations sequence!")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            conn.rollback()

if __name__ == "__main__":
    fix_invitation_sequence()
