"""
Data-Only Migration Script
Copies all data from old database to new database
Assumes schema already exists on target database
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# Database URLs
SOURCE_DB = "postgresql://postgres:jgscsvYlKTLKhjKqVonzKcPebUnHDkdr@centerbeam.proxy.rlwy.net:43363/railway"
TARGET_DB = "postgresql://postgres:vubcsZDyBOcYidQCcypGPNoMrNmnGXuQ@yamanote.proxy.rlwy.net:37987/railway"

# Tables in dependency order
TABLES = [
    'subscriptions',
    'users',
    'contractors',
    'suppliers',
    'subscribers',
    'jobs',
    'unlocked_leads',
    'push_subscriptions',
    'user_invitations'
]

def copy_table(source_engine, target_engine, table_name):
    """Copy all data from source table to target table"""
    print(f"\n{'='*80}")
    print(f"Migrating: {table_name}")
    print(f"{'='*80}")
    
    # Get source count
    try:
        with source_engine.connect() as conn:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            source_count = result.scalar()
    except Exception as e:
        print(f"  ⚠ Table {table_name} doesn't exist in source, skipping")
        return True
    
    print(f"  Source records: {source_count}")
    
    if source_count == 0:
        print(f"  ✓ Table is empty, skipping")
        return True
    
    # Get columns
    with source_engine.connect() as conn:
        result = conn.execute(text(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position
        """))
        columns = [row[0] for row in result.fetchall()]
    
    # Fetch all data
    column_list = ', '.join([f'"{col}"' for col in columns])
    
    print(f"  Fetching {source_count} rows...")
    with source_engine.connect() as source_conn:
        source_data = source_conn.execute(text(f"SELECT {column_list} FROM {table_name}")).fetchall()
    
    # Insert data
    print(f"  Inserting into target...")
    with target_engine.connect() as target_conn:
        trans = target_conn.begin()
        
        try:
            # Disable triggers
            target_conn.execute(text(f"ALTER TABLE {table_name} DISABLE TRIGGER ALL"))
            
            # Build insert query
            placeholders = ', '.join([f':{col}' for col in columns])
            insert_query = text(f'INSERT INTO {table_name} ({column_list}) VALUES ({placeholders})')
            
            # Insert in batches
            batch_size = 100
            for i in range(0, len(source_data), batch_size):
                batch = source_data[i:i+batch_size]
                
                for row in batch:
                    row_dict = dict(zip(columns, row))
                    target_conn.execute(insert_query, row_dict)
                
                print(f"    Progress: {min(i+batch_size, len(source_data))}/{len(source_data)}")
            
            # Re-enable triggers
            target_conn.execute(text(f"ALTER TABLE {table_name} ENABLE TRIGGER ALL"))
            
            # Reset sequence
            try:
                result = target_conn.execute(text(f"SELECT pg_get_serial_sequence('{table_name}', 'id')"))
                sequence_name = result.scalar()
                if sequence_name:
                    target_conn.execute(text(f"SELECT setval('{sequence_name}', COALESCE((SELECT MAX(id) FROM {table_name}), 1), true)"))
            except:
                pass
            
            # Commit
            trans.commit()
            print(f"  ✓ Committed")
            
        except Exception as e:
            trans.rollback()
            print(f"  ✗ Rolled back: {e}")
            raise e
    
    # Verify
    with target_engine.connect() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        target_count = result.scalar()
    
    if source_count == target_count:
        print(f"  ✓ SUCCESS: {target_count} records migrated")
        return True
    else:
        print(f"  ✗ MISMATCH: Source={source_count}, Target={target_count}")
        return False

def main():
    print("="*80)
    print("DATA MIGRATION - Old Railway → New Railway")
    print("="*80)
    print(f"\nSource: centerbeam.proxy.rlwy.net:43363")
    print(f"Target: yamanote.proxy.rlwy.net:37987")
    print("\n" + "="*80)
    
    # Create engines
    print("\nConnecting to databases...")
    source_engine = create_engine(SOURCE_DB, pool_pre_ping=True, isolation_level="AUTOCOMMIT")
    target_engine = create_engine(TARGET_DB, pool_pre_ping=True)
    
    # Test connections
    try:
        with source_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✓ Connected to source")
    except Exception as e:
        print(f"✗ Source connection failed: {e}")
        return
    
    try:
        with target_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✓ Connected to target")
    except Exception as e:
        print(f"✗ Target connection failed: {e}")
        return
    
    # Migrate tables
    print("\n" + "="*80)
    print("Starting Data Migration")
    print("="*80)
    
    success = 0
    failed = []
    
    for table in TABLES:
        try:
            if copy_table(source_engine, target_engine, table):
                success += 1
            else:
                failed.append(table)
        except Exception as e:
            print(f"\n✗ Error: {e}")
            failed.append(table)
    
    # Summary
    print("\n" + "="*80)
    print("MIGRATION SUMMARY")
    print("="*80)
    print(f"Total tables: {len(TABLES)}")
    print(f"Successfully migrated: {success}")
    print(f"Failed: {len(failed)}")
    
    if failed:
        print(f"\nFailed tables: {', '.join(failed)}")
    
    print("\n" + "="*80)
    
    if len(failed) == 0:
        print("✓✓✓ MIGRATION COMPLETED SUCCESSFULLY ✓✓✓")
        print("\nNext steps:")
        print("1. Run: .\\Tiger_leads\\Scripts\\python.exe verify_migration.py")
        print("2. Test the application")
    else:
        print("✗✗✗ MIGRATION COMPLETED WITH ERRORS ✗✗✗")
    
    print("="*80)
    
    # Cleanup
    source_engine.dispose()
    target_engine.dispose()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✗ Cancelled")
    except Exception as e:
        print(f"\n\n✗ Failed: {e}")
        import traceback
        traceback.print_exc()
