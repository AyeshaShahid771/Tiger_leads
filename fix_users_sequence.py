"""
Fix users table sequence issue
The sequence needs to be reset to the max ID + 1
"""
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

print("="*80)
print("FIXING USERS TABLE SEQUENCE")
print("="*80)

with engine.connect() as conn:
    # Check current max ID
    result = conn.execute(text("SELECT MAX(id) FROM users"))
    max_id = result.scalar()
    print(f"\nCurrent max user ID: {max_id}")
    
    # Get sequence name
    result = conn.execute(text("SELECT pg_get_serial_sequence('users', 'id')"))
    seq_name = result.scalar()
    print(f"Sequence name: {seq_name}")
    
    if seq_name:
        # Get current sequence value
        result = conn.execute(text(f"SELECT last_value FROM {seq_name}"))
        current_seq = result.scalar()
        print(f"Current sequence value: {current_seq}")
        
        # Reset sequence to max_id + 1
        new_value = (max_id or 0) + 1
        print(f"\nResetting sequence to: {new_value}")
        
        conn.execute(text(f"SELECT setval('{seq_name}', {new_value}, false)"))
        conn.commit()
        
        # Verify
        result = conn.execute(text(f"SELECT last_value FROM {seq_name}"))
        new_seq = result.scalar()
        print(f"New sequence value: {new_seq}")
        
        print("\n" + "="*80)
        print("✓ Sequence fixed! Next user ID will be:", new_value)
        print("="*80)
    else:
        print("\n✗ No sequence found for users.id")

engine.dispose()
