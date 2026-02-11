"""
Verify Foreign Key Constraints in Target Database
"""
from sqlalchemy import create_engine, text

TARGET_DB = "postgresql://postgres:vubcsZDyBOcYidQCcypGPNoMrNmnGXuQ@yamanote.proxy.rlwy.net:37987/railway"

def main():
    engine = create_engine(TARGET_DB)
    
    query = text("""
        SELECT
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name,
            tc.constraint_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
        ORDER BY tc.table_name, kcu.column_name
    """)
    
    print("=" * 120)
    print("FOREIGN KEY CONSTRAINTS IN TARGET DATABASE")
    print("=" * 120)
    print(f"{'Table':<25} {'Column':<25} {'References Table':<25} {'References Column':<25} {'Constraint'}")
    print("-" * 120)
    
    with engine.connect() as conn:
        result = conn.execute(query)
        count = 0
        for row in result:
            print(f"{row.table_name:<25} {row.column_name:<25} {row.foreign_table_name:<25} {row.foreign_column_name:<25} {row.constraint_name}")
            count += 1
    
    print("-" * 120)
    print(f"Total Foreign Key Constraints: {count}")
    print("=" * 120)
    
    if count > 0:
        print("\n✓ Foreign keys are present in target database")
    else:
        print("\n✗ WARNING: No foreign keys found!")
    
    engine.dispose()

if __name__ == "__main__":
    main()
