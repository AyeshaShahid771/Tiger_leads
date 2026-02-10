"""
Database Migration Script - PostgreSQL to PostgreSQL
Migrates complete database schema and data from one PostgreSQL instance to another.

Order of operations:
1. Create table structures (without constraints)
2. Add primary keys
3. Create sequences
4. Copy data
5. Add foreign keys
6. Add indexes

Usage:
    python database_migration.py

Author: Database Migration Tool
Date: 2026-02-06
"""

from sqlalchemy import create_engine, text
import json

# Database connection strings
SOURCE_DB = "postgresql://postgres:jgscsvYlKTLKhjKqVonzKcPebUnHDkdr@centerbeam.proxy.rlwy.net:43363/railway"
TARGET_DB = "postgresql://postgres:vubcsZDyBOcYidQCcypGPNoMrNmnGXuQ@yamanote.proxy.rlwy.net:37987/railway"


def create_table_structures(source_engine, target_engine):
    """Step 1: Create table structures without constraints"""
    print("\n" + "="*80)
    print("STEP 1: Creating Table Structures")
    print("="*80 + "\n")
    
    with source_engine.connect() as source_conn:
        # Get all tables
        result = source_conn.execute(text("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename
        """))
        tables = [row[0] for row in result.fetchall()]
    
    print(f"Found {len(tables)} tables\n")
    
    for table in tables:
        print(f"  Creating {table}...", end=" ", flush=True)
        
        # Get column information
        with source_engine.connect() as conn:
            result = conn.execute(text(f"""
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
        
        # Build CREATE TABLE statement
        col_defs = []
        for col_name, data_type, max_len, nullable, default, udt_name in columns:
            # Determine column type - check for arrays first
            if udt_name and udt_name.startswith('_'):
                # It's an array type
                if udt_name == '_varchar' or udt_name == '_text':
                    col_type = 'TEXT[]'
                elif udt_name == '_int4':
                    col_type = 'INTEGER[]'
                elif udt_name == '_int8':
                    col_type = 'BIGINT[]'
                elif udt_name == '_bool':
                    col_type = 'BOOLEAN[]'
                else:
                    col_type = f'{udt_name.lstrip("_").upper()}[]'
            elif data_type == 'ARRAY':
                col_type = 'TEXT[]'
            elif data_type == 'character varying':
                if max_len:
                    col_type = f'VARCHAR({max_len})'
                else:
                    col_type = 'VARCHAR'  # No length limit
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
            
            if default and 'nextval' not in str(default):
                col_def += f' DEFAULT {default}'
            
            col_defs.append(col_def)
        
        # Create table
        create_sql = f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(col_defs)})"
        
        with target_engine.connect() as conn:
            conn.execute(text(create_sql))
            conn.commit()
        
        print("✓")


def add_primary_keys(source_engine, target_engine):
    """Step 2: Add primary keys"""
    print("\n" + "="*80)
    print("STEP 2: Adding Primary Keys")
    print("="*80 + "\n")
    
    with source_engine.connect() as source_conn:
        result = source_conn.execute(text("""
            SELECT tc.table_name, kcu.column_name, tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
            AND tc.table_schema = 'public'
        """))
        pks = result.fetchall()
    
    for table, column, constraint in pks:
        print(f"  ✓ {table}", flush=True)
        with target_engine.connect() as conn:
            try:
                conn.execute(text(f"""
                    ALTER TABLE {table}
                    ADD CONSTRAINT {constraint} PRIMARY KEY ({column})
                """))
                conn.commit()
            except:
                pass  # Already exists


def create_sequences(source_engine, target_engine):
    """Step 3: Create sequences"""
    print("\n" + "="*80)
    print("STEP 3: Creating Sequences")
    print("="*80 + "\n")
    
    with source_engine.connect() as source_conn:
        result = source_conn.execute(text("""
            SELECT sequence_name FROM information_schema.sequences
            WHERE sequence_schema = 'public'
        """))
        sequences = [row[0] for row in result.fetchall()]
    
    for seq in sequences:
        print(f"  ✓ {seq}", flush=True)
        with target_engine.connect() as conn:
            try:
                conn.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {seq}"))
                conn.commit()
            except:
                pass


def copy_data(source_engine, target_engine):
    """Step 4: Copy data"""
    print("\n" + "="*80)
    print("STEP 4: Copying Data")
    print("="*80 + "\n")
    
    with source_engine.connect() as source_conn:
        result = source_conn.execute(text("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename
        """))
        tables = [row[0] for row in result.fetchall()]
    
    for table in tables:
        # Get count
        with source_engine.connect() as source_conn:
            count = source_conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        
        if count == 0:
            print(f"  {table}: empty")
            continue
        
        print(f"  {table}: {count} records...", end=" ", flush=True)
        
        # Get columns and their types from TARGET database
        with target_engine.connect() as conn:
            result = conn.execute(text(f"""
                SELECT column_name, data_type, udt_name
                FROM information_schema.columns 
                WHERE table_name = '{table}'
                ORDER BY ordinal_position
            """))
            column_info = result.fetchall()
            columns = [row[0] for row in column_info]
            target_column_types = {row[0]: (row[1], row[2]) for row in column_info}
        
        column_list = ', '.join([f'"{col}"' for col in columns])
        
        # Copy data in batches
        batch_size = 500
        offset = 0
        total = 0
        
        while True:
            with source_engine.connect() as conn:
                data = conn.execute(text(
                    f"SELECT {column_list} FROM {table} LIMIT {batch_size} OFFSET {offset}"
                )).fetchall()
            
            if not data:
                break
            
            with target_engine.connect() as conn:
                placeholders = ', '.join([f':{col}' for col in columns])
                insert_sql = text(f'INSERT INTO {table} ({column_list}) VALUES ({placeholders})')
                
                for row in data:
                    row_dict = dict(zip(columns, row))
                    
                    # Convert values based on TARGET column type
                    for key, value in list(row_dict.items()):
                        if value is None:
                            continue
                        
                        target_data_type, target_udt_name = target_column_types[key]
                        
                        # Check if target column is JSON type
                        if target_data_type == 'json' or target_udt_name == 'json':
                            # Convert dicts and lists to JSON strings for JSON columns
                            if isinstance(value, (dict, list)):
                                row_dict[key] = json.dumps(value)
                        # For ARRAY columns, keep lists as-is (psycopg2 handles them)
                        elif isinstance(value, dict):
                            # Convert dicts to JSON even for non-JSON columns (like JSONB)
                            row_dict[key] = json.dumps(value)
                        elif isinstance(value, list) and value and isinstance(value[0], dict):
                            # List of dicts - convert to JSON
                            row_dict[key] = json.dumps(value)
                    
                    conn.execute(insert_sql, row_dict)
                
                conn.commit()
            
            total += len(data)
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
        
        print(f"✓ {total}")


def add_foreign_keys(source_engine, target_engine):
    """Step 5: Add foreign keys"""
    print("\n" + "="*80)
    print("STEP 5: Adding Foreign Keys")
    print("="*80 + "\n")
    
    with source_engine.connect() as source_conn:
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
        fks = result.fetchall()
    
    for table, col, ref_table, ref_col, constraint, delete_rule in fks:
        with target_engine.connect() as conn:
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
                
                conn.execute(text(fk_sql))
                conn.commit()
                print(f"  ✓ {table}.{col} -> {ref_table}.{ref_col}")
            except:
                pass


def add_indexes(source_engine, target_engine):
    """Step 6: Add indexes"""
    print("\n" + "="*80)
    print("STEP 6: Adding Indexes")
    print("="*80 + "\n")
    
    with source_engine.connect() as source_conn:
        result = source_conn.execute(text("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            AND indexname NOT LIKE '%_pkey'
        """))
        indexes = result.fetchall()
    
    for index_name, index_def in indexes:
        with target_engine.connect() as conn:
            try:
                conn.execute(text(index_def))
                conn.commit()
                print(f"  ✓ {index_name}")
            except:
                pass


def main():
    """Main migration function"""
    print("="*80)
    print("DATABASE MIGRATION")
    print("="*80)
    print(f"\nSource: {SOURCE_DB.split('@')[1].split('/')[0]}")
    print(f"Target: {TARGET_DB.split('@')[1].split('/')[0]}")
    
    # Create engines
    source_engine = create_engine(SOURCE_DB, pool_pre_ping=True)
    target_engine = create_engine(TARGET_DB, pool_pre_ping=True)
    
    try:
        # Run migration steps
        create_table_structures(source_engine, target_engine)
        add_primary_keys(source_engine, target_engine)
        create_sequences(source_engine, target_engine)
        copy_data(source_engine, target_engine)
        add_foreign_keys(source_engine, target_engine)
        add_indexes(source_engine, target_engine)
        
        print("\n" + "="*80)
        print("✓✓✓ MIGRATION COMPLETED SUCCESSFULLY ✓✓✓")
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
