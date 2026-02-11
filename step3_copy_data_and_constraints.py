"""
Step 3: Copy Data and Add Constraints
Assumes tables, primary keys, and sequences already exist
Only copies data and adds foreign keys/indexes
"""
import json
from sqlalchemy import create_engine, text

SOURCE_DB = "postgresql://postgres:jgscsvYlKTLKhjKqVonzKcPebUnHDkdr@centerbeam.proxy.rlwy.net:43363/railway"
TARGET_DB = "postgresql://postgres:vubcsZDyBOcYidQCcypGPNoMrNmnGXuQ@yamanote.proxy.rlwy.net:37987/railway"

def copy_data(source_engine, target_engine):
    """Copy all data from source to target"""
    print("\n" + "="*80)
    print("COPYING DATA")
    print("="*80)
    
    # Get tables from source
    with source_engine.connect() as conn:
        result = conn.execute(text("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename
        """))
        tables = [row[0] for row in result.fetchall()]
    
    print(f"\nFound {len(tables)} tables to migrate\n")
    
    success = 0
    failed = []
    
    for table in tables:
        try:
            # Get count from source
            with source_engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                source_count = result.scalar()
            
            # Check if target already has data
            with target_engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                target_count = result.scalar()
            
            if target_count > 0:
                print(f"  {table}: skipping ({target_count} records already exist)")
                success += 1
                continue
            
            if source_count == 0:
                print(f"  {table}: empty")
                success += 1
                continue
            
            print(f"  {table}: copying {source_count} records...", end=" ", flush=True)
            
            # Get columns and their types from both source and target
            with source_engine.connect() as conn:
                result = conn.execute(text(f"""
                    SELECT column_name, data_type, udt_name
                    FROM information_schema.columns 
                    WHERE table_name = '{table}'
                    ORDER BY ordinal_position
                """))
                column_info = result.fetchall()
                columns = [row[0] for row in column_info]
                source_column_types = {row[0]: (row[1], row[2]) for row in column_info}
            
            # Get target column types to handle schema mismatches
            with target_engine.connect() as conn:
                result = conn.execute(text(f"""
                    SELECT column_name, data_type, udt_name
                    FROM information_schema.columns 
                    WHERE table_name = '{table}'
                    ORDER BY ordinal_position
                """))
                target_column_types = {row[0]: (row[1], row[2]) for row in result.fetchall()}
            
            # Fetch data in batches
            column_list = ', '.join([f'"{col}"' for col in columns])
            
            # Process in batches to avoid memory issues
            batch_size = 500
            offset = 0
            total_inserted = 0
            
            while True:
                # Fetch batch from source
                with source_engine.connect() as conn:
                    data = conn.execute(text(
                        f"SELECT {column_list} FROM {table} LIMIT {batch_size} OFFSET {offset}"
                    )).fetchall()
                
                if not data:
                    break
                
                # Insert batch into target
                with target_engine.connect() as conn:
                    for row in data:
                        row_dict = dict(zip(columns, row))
                        
                        # Convert values based on column type
                        for key, value in list(row_dict.items()):
                            if value is None:
                                continue
                            
                            data_type, udt_name = column_types[key]
                            
                            if isinstance(value, dict):
                                # Convert dict to JSON string
                                row_dict[key] = json.dumps(value)
                            elif isinstance(value, list):
                                # Check if it's an array column
                                if data_type == 'ARRAY' or udt_name.startswith('_'):
                                    # It's a PostgreSQL array - keep as list, psycopg2 will handle it
                                    pass
                                elif value and isinstance(value[0], dict):
                                    # List of dicts - convert to JSON
                                    row_dict[key] = json.dumps(value)
                        
                        # Build parameterized insert
                        placeholders = ', '.join([f':{col}' for col in columns])
                        insert_sql = text(f'INSERT INTO {table} ({column_list}) VALUES ({placeholders})')
                        conn.execute(insert_sql, row_dict)
                        
                        total_inserted += 1
                        
                        # Show progress for each record
                        if total_inserted % 10 == 0:
                            print(f"{total_inserted}...", end=" ", flush=True)
                        elif total_inserted <= 10:
                            print(f"{total_inserted}...", end=" ", flush=True)
                    
                    conn.commit()
                
                offset += batch_size
            
            # Reset sequence
            with target_engine.connect() as conn:
                try:
                    result = conn.execute(text(f"SELECT pg_get_serial_sequence('{table}', 'id')"))
                    seq = result.scalar()
                    if seq:
                        conn.execute(text(
                            f"SELECT setval('{seq}', COALESCE((SELECT MAX(id) FROM {table}), 1), true)"
                        ))
                        conn.commit()
                except:
                    pass
            
            print(f"✓ {total_inserted} records")
            success += 1
            
        except Exception as e:
            print(f"✗ Error: {str(e)[:100]}")
            failed.append(table)
    
    print(f"\n{'='*80}")
    print(f"Data Migration Summary: {success}/{len(tables)} tables")
    if failed:
        print(f"Failed: {', '.join(failed)}")
    print(f"{'='*80}")
    
    return len(failed) == 0

def add_foreign_keys(source_engine, target_engine):
    """Add foreign keys"""
    print("\n" + "="*80)
    print("ADDING FOREIGN KEYS")
    print("="*80 + "\n")
    
    with source_engine.connect() as source_conn, target_engine.connect() as target_conn:
        # Get all foreign keys from source
        result = source_conn.execute(text("""
            SELECT
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name,
                tc.constraint_name,
                rc.delete_rule
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            JOIN information_schema.referential_constraints AS rc
                ON tc.constraint_name = rc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
            ORDER BY tc.table_name, kcu.column_name
        """))
        
        fks = result.fetchall()
        
        if not fks:
            print("  No foreign keys found")
            return
        
        print(f"Found {len(fks)} foreign keys\n")
        
        added = 0
        skipped = 0
        
        for row in fks:
            table, col, ref_table, ref_col, constraint, delete_rule = row
            
            # Check if FK already exists
            check_result = target_conn.execute(text(f"""
                SELECT COUNT(*) 
                FROM information_schema.table_constraints 
                WHERE constraint_name = '{constraint}'
            """))
            
            if check_result.scalar() > 0:
                skipped += 1
                continue
            
            try:
                fk_sql = f"""
                    ALTER TABLE {table}
                    ADD CONSTRAINT {constraint}
                    FOREIGN KEY ({col})
                    REFERENCES {ref_table}({ref_col})
                """
                
                if delete_rule == 'CASCADE':
                    fk_sql += " ON DELETE CASCADE"
                elif delete_rule == 'SET NULL':
                    fk_sql += " ON DELETE SET NULL"
                
                target_conn.execute(text(fk_sql))
                target_conn.commit()
                added += 1
                print(f"  ✓ {table}.{col} -> {ref_table}.{ref_col}")
            except Exception as e:
                print(f"  ⚠ {table}.{col}: {str(e)[:80]}")
        
        print(f"\n{'='*80}")
        print(f"Foreign Keys: {added} added, {skipped} already existed")
        print(f"{'='*80}")

def add_indexes(source_engine, target_engine):
    """Add indexes"""
    print("\n" + "="*80)
    print("ADDING INDEXES")
    print("="*80 + "\n")
    
    with source_engine.connect() as source_conn, target_engine.connect() as target_conn:
        # Get all indexes from source (excluding primary keys)
        result = source_conn.execute(text("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            AND indexname NOT LIKE '%_pkey'
            ORDER BY indexname
        """))
        
        indexes = result.fetchall()
        
        if not indexes:
            print("  No indexes found")
            return
        
        print(f"Found {len(indexes)} indexes\n")
        
        added = 0
        skipped = 0
        
        for index_name, index_def in indexes:
            # Check if index already exists
            check_result = target_conn.execute(text(f"""
                SELECT COUNT(*) 
                FROM pg_indexes 
                WHERE indexname = '{index_name}'
            """))
            
            if check_result.scalar() > 0:
                skipped += 1
                continue
            
            try:
                target_conn.execute(text(index_def))
                target_conn.commit()
                added += 1
                print(f"  ✓ {index_name}")
            except Exception as e:
                print(f"  ⚠ {index_name}: {str(e)[:80]}")
        
        print(f"\n{'='*80}")
        print(f"Indexes: {added} added, {skipped} already existed")
        print(f"{'='*80}")

def main():
    print("="*80)
    print("DATABASE MIGRATION - DATA AND CONSTRAINTS")
    print("="*80)
    print("\nAssuming tables, primary keys, and sequences already exist")
    print("This script will:")
    print("  1. Copy all data from source to target")
    print("  2. Add foreign key constraints")
    print("  3. Add indexes")
    
    # Create engines with connection pooling
    source_engine = create_engine(
        SOURCE_DB, 
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10
    )
    target_engine = create_engine(
        TARGET_DB, 
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10
    )
    
    # Test connections
    print("\nTesting connections...")
    try:
        with source_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✓ Source connected")
    except Exception as e:
        print(f"✗ Source failed: {e}")
        return
    
    try:
        with target_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✓ Target connected")
    except Exception as e:
        print(f"✗ Target failed: {e}")
        return
    
    try:
        # Step 1: Copy data
        data_success = copy_data(source_engine, target_engine)
        
        # Step 2: Add foreign keys
        add_foreign_keys(source_engine, target_engine)
        
        # Step 3: Add indexes
        add_indexes(source_engine, target_engine)
        
        print("\n" + "="*80)
        if data_success:
            print("✓✓✓ MIGRATION COMPLETED SUCCESSFULLY ✓✓✓")
            print("\nNext steps:")
            print("1. Run: .\\Tiger_leads\\Scripts\\python.exe verify_migration.py")
            print("2. Update .env to new database")
            print("3. Test application")
        else:
            print("⚠⚠⚠ MIGRATION COMPLETED WITH SOME ERRORS ⚠⚠⚠")
            print("Review errors above and retry failed tables if needed")
        print("="*80)
        
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        source_engine.dispose()
        target_engine.dispose()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✗ Cancelled by user")
    except Exception as e:
        print(f"\n\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
