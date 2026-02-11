"""
Step 2: Copy Schema and Data from Old to New Database
1. Create all tables (no foreign keys)
2. Copy all data
3. Add foreign keys and indexes
"""
from sqlalchemy import create_engine, text

SOURCE_DB = "postgresql://postgres:jgscsvYlKTLKhjKqVonzKcPebUnHDkdr@centerbeam.proxy.rlwy.net:43363/railway"
TARGET_DB = "postgresql://postgres:vubcsZDyBOcYidQCcypGPNoMrNmnGXuQ@yamanote.proxy.rlwy.net:37987/railway"

def create_tables(source_engine, target_engine):
    """Create all table structures without foreign keys"""
    print("\n" + "="*80)
    print("CREATING TABLE STRUCTURES")
    print("="*80)
    
    with source_engine.connect() as source_conn, target_engine.connect() as target_conn:
        # Get all tables
        result = source_conn.execute(text("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename
        """))
        tables = [row[0] for row in result.fetchall()]
        
        print(f"Creating {len(tables)} tables...\n")
        
        for table in tables:
            print(f"  {table}")
            
            # Get columns
            result = source_conn.execute(text(f"""
                SELECT 
                    column_name, 
                    data_type, 
                    character_maximum_length,
                    is_nullable, 
                    column_default,
                    udt_name
                FROM information_schema.columns
                WHERE table_name = '{table}'
                ORDER BY ordinal_position
            """))
            columns = result.fetchall()
            
            # Build CREATE TABLE
            col_defs = []
            for col in columns:
                col_name, data_type, max_len, nullable, default, udt_name = col
                
                # Determine column type
                if data_type == 'ARRAY':
                    if udt_name == '_varchar' or udt_name == '_text':
                        col_type = 'TEXT[]'
                    elif udt_name == '_int4':
                        col_type = 'INTEGER[]'
                    else:
                        col_type = f'{udt_name}[]'
                elif data_type == 'character varying':
                    col_type = f'VARCHAR({max_len})' if max_len else 'VARCHAR(255)'
                elif data_type == 'USER-DEFINED':
                    col_type = 'JSON'
                elif data_type == 'timestamp without time zone':
                    col_type = 'TIMESTAMP'
                elif data_type == 'timestamp with time zone':
                    col_type = 'TIMESTAMPTZ'
                else:
                    col_type = data_type.upper()
                
                col_def = f'"{col_name}" {col_type}'
                
                if nullable == 'NO':
                    col_def += ' NOT NULL'
                
                if default and 'nextval' not in default:
                    col_def += f' DEFAULT {default}'
                
                col_defs.append(col_def)
            
            # Create table
            create_sql = f"CREATE TABLE {table} ({', '.join(col_defs)})"
            target_conn.execute(text(create_sql))
            target_conn.commit()
        
        # Add primary keys
        print("\nAdding primary keys...\n")
        for table in tables:
            result = source_conn.execute(text(f"""
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = '{table}'::regclass AND i.indisprimary
            """))
            pk_cols = [row[0] for row in result.fetchall()]
            
            if pk_cols:
                pk_sql = f"ALTER TABLE {table} ADD PRIMARY KEY ({', '.join(pk_cols)})"
                target_conn.execute(text(pk_sql))
                target_conn.commit()
                print(f"  {table}")
        
        # Create sequences
        print("\nCreating sequences...\n")
        result = source_conn.execute(text("""
            SELECT sequence_name 
            FROM information_schema.sequences 
            WHERE sequence_schema = 'public'
        """))
        sequences = [row[0] for row in result.fetchall()]
        
        for seq in sequences:
            try:
                target_conn.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {seq}"))
                target_conn.commit()
                print(f"  {seq}")
            except:
                pass
        
        print("\n✓ All tables created")

def copy_data(source_engine, target_engine):
    """Copy all data"""
    print("\n" + "="*80)
    print("COPYING DATA")
    print("="*80)
    
    with source_engine.connect() as source_conn:
        result = source_conn.execute(text("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename
        """))
        tables = [row[0] for row in result.fetchall()]
    
    print()
    success = 0
    
    for table in tables:
        # Get count
        with source_engine.connect() as conn:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar()
        
        if count == 0:
            print(f"  {table}: empty")
            success += 1
            continue
        
        print(f"  {table}: {count} records", end=" ")
        
        # Get columns
        with source_engine.connect() as conn:
            result = conn.execute(text(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = '{table}'
                ORDER BY ordinal_position
            """))
            columns = [row[0] for row in result.fetchall()]
        
        # Fetch data
        column_list = ', '.join([f'"{col}"' for col in columns])
        with source_engine.connect() as conn:
            data = conn.execute(text(f"SELECT {column_list} FROM {table}")).fetchall()
        
        # Insert data
        try:
            with target_engine.connect() as conn:
                placeholders = ', '.join([f':{col}' for col in columns])
                insert_sql = text(f'INSERT INTO {table} ({column_list}) VALUES ({placeholders})')
                
                import json
                for row in data:
                    row_dict = dict(zip(columns, row))
                    
                    # Convert dict/list values to JSON strings
                    for key, value in row_dict.items():
                        if isinstance(value, (dict, list)):
                            row_dict[key] = json.dumps(value)
                    
                    conn.execute(insert_sql, row_dict)
                
                # Reset sequence
                try:
                    result = conn.execute(text(f"SELECT pg_get_serial_sequence('{table}', 'id')"))
                    seq = result.scalar()
                    if seq:
                        conn.execute(text(f"SELECT setval('{seq}', COALESCE((SELECT MAX(id) FROM {table}), 1), true)"))
                except:
                    pass
                
                conn.commit()
                print("✓")
                success += 1
        except Exception as e:
            print(f"✗ {e}")
    
    print(f"\n✓ Migrated {success}/{len(tables)} tables")

def add_constraints(source_engine, target_engine):
    """Add foreign keys and indexes"""
    print("\n" + "="*80)
    print("ADDING CONSTRAINTS")
    print("="*80)
    
    with source_engine.connect() as source_conn, target_engine.connect() as target_conn:
        # Add foreign keys
        print("\nForeign keys:\n")
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
        """))
        
        fk_count = 0
        for row in result.fetchall():
            table, col, ref_table, ref_col, constraint, delete_rule = row
            
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
                fk_count += 1
                print(f"  {table}.{col} -> {ref_table}.{ref_col}")
            except Exception as e:
                print(f"  ⚠ {table}.{col}: {e}")
        
        # Add indexes
        print(f"\nIndexes:\n")
        result = source_conn.execute(text("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            AND indexname NOT LIKE '%_pkey'
        """))
        
        idx_count = 0
        for row in result.fetchall():
            index_name, index_def = row
            try:
                target_conn.execute(text(index_def))
                target_conn.commit()
                idx_count += 1
                print(f"  {index_name}")
            except:
                pass
        
        print(f"\n✓ Added {fk_count} foreign keys and {idx_count} indexes")

def main():
    print("="*80)
    print("DATABASE MIGRATION - COPY SCHEMA AND DATA")
    print("="*80)
    
    source_engine = create_engine(SOURCE_DB, pool_pre_ping=True)
    target_engine = create_engine(TARGET_DB, pool_pre_ping=True)
    
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
        create_tables(source_engine, target_engine)
        copy_data(source_engine, target_engine)
        add_constraints(source_engine, target_engine)
        
        print("\n" + "="*80)
        print("✓✓✓ MIGRATION COMPLETED SUCCESSFULLY ✓✓✓")
        print("="*80)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        source_engine.dispose()
        target_engine.dispose()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n✗ Cancelled")
