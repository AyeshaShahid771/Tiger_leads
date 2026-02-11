"""
Check all tables for missing sequences
"""
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

print("="*80)
print("CHECKING ALL TABLES FOR SEQUENCES")
print("="*80 + "\n")

with engine.connect() as conn:
    # Get all tables
    result = conn.execute(text("""
        SELECT tablename FROM pg_tables 
        WHERE schemaname = 'public'
        ORDER BY tablename
    """))
    tables = [row[0] for row in result.fetchall()]
    
    missing_sequences = []
    
    for table in tables:
        # Check if table has an id column
        result = conn.execute(text(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = '{table}' AND column_name = 'id'
        """))
        
        if result.fetchone():
            # Check for sequence
            result = conn.execute(text(f"SELECT pg_get_serial_sequence('{table}', 'id')"))
            seq_name = result.scalar()
            
            if seq_name:
                print(f"✓ {table:30} has sequence: {seq_name}")
            else:
                print(f"✗ {table:30} MISSING SEQUENCE!")
                missing_sequences.append(table)

print("\n" + "="*80)
if missing_sequences:
    print(f"⚠ {len(missing_sequences)} tables missing sequences:")
    for table in missing_sequences:
        print(f"  - {table}")
else:
    print("✓ All tables have proper sequences!")
print("="*80)

engine.dispose()
