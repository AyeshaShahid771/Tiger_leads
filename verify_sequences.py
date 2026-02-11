"""
Verify Database Sequences in Target Database
"""
from sqlalchemy import create_engine, text

TARGET_DB = "postgresql://postgres:vubcsZDyBOcYidQCcypGPNoMrNmnGXuQ@yamanote.proxy.rlwy.net:37987/railway"

def main():
    engine = create_engine(TARGET_DB)
    
    query = text("""
        SELECT 
            schemaname,
            sequencename,
            last_value
        FROM pg_sequences
        WHERE schemaname = 'public'
        ORDER BY sequencename
    """)
    
    print("=" * 100)
    print("SEQUENCES IN TARGET DATABASE")
    print("=" * 100)
    print(f"{'Sequence Name':<50} {'Last Value':<20} {'Status'}")
    print("-" * 100)
    
    with engine.connect() as conn:
        result = conn.execute(query)
        count = 0
        for row in result:
            status = "✓ OK" if row.last_value > 0 else "⚠ ZERO"
            print(f"{row.sequencename:<50} {row.last_value:<20} {status}")
            count += 1
    
    print("-" * 100)
    print(f"Total Sequences: {count}")
    print("=" * 100)
    
    if count > 0:
        print("\n✓ Sequences are present in target database")
    else:
        print("\n✗ WARNING: No sequences found!")
    
    engine.dispose()

if __name__ == "__main__":
    main()
