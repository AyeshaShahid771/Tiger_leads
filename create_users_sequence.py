"""
Create sequence for users table and set it as default for id column
"""
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

print("="*80)
print("CREATING AND ATTACHING SEQUENCE TO USERS.ID")
print("="*80)

with engine.connect() as conn:
    # Check current max ID
    result = conn.execute(text("SELECT MAX(id) FROM users"))
    max_id = result.scalar()
    print(f"\nCurrent max user ID: {max_id}")
    
    # Create sequence if it doesn't exist
    print("\nCreating sequence users_id_seq...")
    try:
        conn.execute(text("CREATE SEQUENCE IF NOT EXISTS users_id_seq"))
        conn.commit()
        print("✓ Sequence created")
    except Exception as e:
        print(f"Sequence might already exist: {e}")
    
    # Set sequence to start from max_id + 1
    next_id = (max_id or 0) + 1
    print(f"\nSetting sequence to start from: {next_id}")
    conn.execute(text(f"SELECT setval('users_id_seq', {next_id}, false)"))
    conn.commit()
    
    # Attach sequence to id column as default
    print("\nAttaching sequence to users.id column...")
    conn.execute(text("""
        ALTER TABLE users 
        ALTER COLUMN id SET DEFAULT nextval('users_id_seq')
    """))
    conn.commit()
    print("✓ Sequence attached to id column")
    
    # Set sequence ownership
    print("\nSetting sequence ownership...")
    conn.execute(text("ALTER SEQUENCE users_id_seq OWNED BY users.id"))
    conn.commit()
    print("✓ Sequence ownership set")
    
    # Verify
    result = conn.execute(text("SELECT pg_get_serial_sequence('users', 'id')"))
    seq_name = result.scalar()
    print(f"\nVerification - Sequence name: {seq_name}")
    
    if seq_name:
        result = conn.execute(text(f"SELECT last_value FROM {seq_name}"))
        current_value = result.scalar()
        print(f"Current sequence value: {current_value}")
    
    print("\n" + "="*80)
    print("✓ USERS TABLE SEQUENCE FIXED!")
    print(f"Next user ID will be: {next_id}")
    print("="*80)

engine.dispose()
