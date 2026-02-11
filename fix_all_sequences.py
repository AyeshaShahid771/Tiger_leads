"""
Fix all missing sequences for tables with id columns
"""
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

print("="*80)
print("FIXING ALL MISSING SEQUENCES")
print("="*80 + "\n")

# List of all tables that need sequences
tables_to_fix = [
    'admin_users', 'contractors', 'draft_jobs', 'jobs', 'not_interested_jobs',
    'notifications', 'password_resets', 'payments', 'pending_jurisdictions',
    'push_subscriptions', 'saved_jobs', 'subscribers', 'subscriptions',
    'suppliers', 'temp_documents', 'unlocked_leads', 'user_invitations'
]

with engine.connect() as conn:
    for table in tables_to_fix:
        print(f"\nFixing {table}...")
        
        try:
            # Get max ID
            result = conn.execute(text(f"SELECT MAX(id) FROM {table}"))
            max_id = result.scalar()
            next_id = (max_id or 0) + 1
            print(f"  Max ID: {max_id}, Next ID: {next_id}")
            
            # Create sequence
            seq_name = f"{table}_id_seq"
            conn.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {seq_name}"))
            
            # Set sequence value
            conn.execute(text(f"SELECT setval('{seq_name}', {next_id}, false)"))
            
            # Attach to column
            conn.execute(text(f"""
                ALTER TABLE {table} 
                ALTER COLUMN id SET DEFAULT nextval('{seq_name}')
            """))
            
            # Set ownership
            conn.execute(text(f"ALTER SEQUENCE {seq_name} OWNED BY {table}.id"))
            
            conn.commit()
            print(f"  ✓ Sequence {seq_name} created and attached")
            
        except Exception as e:
            print(f"  ✗ Error: {str(e)[:100]}")
            conn.rollback()

print("\n" + "="*80)
print("VERIFICATION")
print("="*80 + "\n")

# Verify all sequences
with engine.connect() as conn:
    for table in tables_to_fix:
        result = conn.execute(text(f"SELECT pg_get_serial_sequence('{table}', 'id')"))
        seq_name = result.scalar()
        if seq_name:
            print(f"✓ {table:30} → {seq_name}")
        else:
            print(f"✗ {table:30} STILL MISSING!")

print("\n" + "="*80)
print("✓ ALL SEQUENCES FIXED!")
print("="*80)

engine.dispose()
