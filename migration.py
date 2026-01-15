import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2.extras import Json
import sys
from datetime import datetime
import json

# Database connection strings
SOURCE_DB = "postgresql://postgres:MfxAqmdsoKRvATHsVcRinyMaFgwteIpT@ballast.proxy.rlwy.net:57684/railway"
TARGET_DB = "postgresql://postgres:jgscsvYlKTLKhjKqVonzKcPebUnHDkdr@centerbeam.proxy.rlwy.net:43363/railway"

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def connect(db_url):
    return psycopg2.connect(db_url)

def get_tables(cur):
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema='public'
          AND table_type='BASE TABLE'
        ORDER BY table_name;
    """)
    return [r[0] for r in cur.fetchall()]

def get_table_schema(cur, table):
    cur.execute("""
        SELECT
            column_name,
            data_type,
            udt_name,
            character_maximum_length,
            numeric_precision,
            numeric_scale,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_schema='public'
          AND table_name=%s
        ORDER BY ordinal_position;
    """, (table,))

    columns = []
    sequences = []

    for row in cur.fetchall():
        name = row[0]
        dtype = row[1]
        udt = row[2]
        char_len = row[3]
        prec = row[4]
        scale = row[5]
        nullable = row[6]
        default = row[7]

        # Handle arrays
        if dtype == 'ARRAY':
            base_type = udt.lstrip('_')
            if base_type == 'text':
                base_type = 'text'
            elif base_type == 'int4':
                base_type = 'integer'
            elif base_type == 'int8':
                base_type = 'bigint'
            elif base_type == 'int2':
                base_type = 'smallint'
            elif base_type == 'float8':
                base_type = 'double precision'
            elif base_type == 'float4':
                base_type = 'real'
            col_type = f"{base_type}[]"
        elif udt == 'int4':
            col_type = 'integer'
        elif udt == 'int8':
            col_type = 'bigint'
        elif udt == 'int2':
            col_type = 'smallint'
        elif udt == 'bool':
            col_type = 'boolean'
        elif dtype in ('numeric', 'decimal') and prec:
            col_type = f"numeric({prec},{scale or 0})"
        elif char_len:
            col_type = f"{dtype}({char_len})"
        else:
            col_type = dtype

        # Detect sequences (serial/bigserial)
        if default and 'nextval' in default:
            seq_name = default.split("'")[1]
            sequences.append(f'CREATE SEQUENCE IF NOT EXISTS {seq_name};')

        # Column definition
        col = f'"{name}" {col_type}'
        if nullable == 'NO':
            col += " NOT NULL"
        if default:
            col += f" DEFAULT {default}"

        columns.append(col)

    full_sql = ''
    if sequences:
        full_sql += '\n'.join(sequences) + '\n'
    full_sql += f'CREATE TABLE "{table}" (\n  ' + ',\n  '.join(columns) + '\n);'
    return full_sql

def get_primary_key(cur, table):
    cur.execute("""
        SELECT kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
        WHERE tc.constraint_type='PRIMARY KEY'
          AND tc.table_schema='public'
          AND tc.table_name=%s
        ORDER BY kcu.ordinal_position;
    """, (table,))
    cols = [r[0] for r in cur.fetchall()]
    if not cols:
        return None
    col_list = ', '.join(f'"{c}"' for c in cols)
    return f'ALTER TABLE "{table}" ADD PRIMARY KEY ({col_list});'

def get_column_names(cur, table):
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public'
          AND table_name=%s
        ORDER BY ordinal_position;
    """, (table,))
    return [r[0] for r in cur.fetchall()]

def get_column_types(cur, table):
    cur.execute("""
        SELECT column_name, data_type, udt_name
        FROM information_schema.columns
        WHERE table_schema='public'
          AND table_name=%s
        ORDER BY ordinal_position;
    """, (table,))
    return {r[0]: (r[1], r[2]) for r in cur.fetchall()}

def migrate():
    src = connect(SOURCE_DB)
    tgt = connect(TARGET_DB)
    tgt.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

    sc = src.cursor()
    tc = tgt.cursor()

    try:
        tables = get_tables(sc)
        log(f"Found tables: {', '.join(tables)}")

        # Step 1: Create tables + sequences + primary keys
        for t in tables:
            log(f"Creating table {t}")
            tc.execute(f'DROP TABLE IF EXISTS "{t}" CASCADE;')
            schema_sql = get_table_schema(sc, t)
            tc.execute(schema_sql)
            pk_sql = get_primary_key(sc, t)
            if pk_sql:
                tc.execute(pk_sql)

        # Step 2: Copy data with batching
        # Separate jobs table to process it last (it takes longer)
        regular_tables = [t for t in tables if t != 'jobs']
        jobs_table = [t for t in tables if t == 'jobs']
        
        # Process regular tables first
        tables_to_process = regular_tables + jobs_table
        
        BATCH_SIZE = 500
        for t in tables_to_process:
            log(f"Copying data for {t}...")
            
            # Get column info FIRST before creating any cursors
            cols = get_column_names(sc, t)
            if not cols:
                log(f"WARNING: Table {t} has no columns, skipping...")
                continue
            
            col_types = get_column_types(sc, t)
            
            # Check row count
            sc_check = src.cursor()
            sc_check.execute(f'SELECT COUNT(*) FROM "{t}";')
            row_count = sc_check.fetchone()[0]
            sc_check.close()
            
            if row_count == 0:
                log(f"Table {t} is empty, skipping data copy...")
                continue
            
            log(f"Table {t} has {row_count} rows, copying...")
            
            # Create server-side cursor for fetching data
            sc2 = src.cursor(name=f"cursor_{t}")
            sc2.itersize = BATCH_SIZE
            sc2.execute(f'SELECT * FROM "{t}";')

            col_list = ', '.join(f'"{c}"' for c in cols)
            placeholders = ', '.join(['%s'] * len(cols))

            rows_copied = 0
            while True:
                batch = sc2.fetchmany(BATCH_SIZE)
                if not batch:
                    break

                # psycopg2 handles most conversions automatically
                batch_fixed = []
                for row in batch:
                    fixed_row = []
                    for idx, val in enumerate(row):
                        if val is None:
                            fixed_row.append(None)
                        else:
                            col_name = cols[idx]
                            data_type, udt_name = col_types.get(col_name, (None, None))
                            
                            # For JSON/JSONB, use Json adapter
                            if data_type in ('json', 'jsonb') and isinstance(val, (dict, list)):
                                fixed_row.append(Json(val))
                            else:
                                # For arrays and all other types, let psycopg2 handle it
                                fixed_row.append(val)
                    batch_fixed.append(tuple(fixed_row))

                # Insert batch
                for r in batch_fixed:
                    try:
                        tc.execute(f'INSERT INTO "{t}" ({col_list}) VALUES ({placeholders});', r)
                        rows_copied += 1
                        if rows_copied % 100 == 0:
                            log(f"Inserted {rows_copied}/{row_count} rows into {t}")
                    except Exception as e:
                        log(f"ERROR inserting row {rows_copied + 1} into {t}: {e}")
                        log(f"Problematic row (first 3 values): {r[:3]}")
                        raise

            sc2.close()
            log(f"✅ Finished copying {rows_copied} rows into {t}")

        log("🎉 SUCCESS: MIGRATION COMPLETED SUCCESSFULLY")

    except Exception as e:
        log(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        sc.close()
        tc.close()
        src.close()
        tgt.close()
        log("Connections closed")

if __name__ == "__main__":
    print("="*60)
    print("DATABASE MIGRATION SCRIPT")
    print("="*60)
    print(f"Source: {SOURCE_DB.split('@')[1]}")
    print(f"Target: {TARGET_DB.split('@')[1]}")
    print("="*60)

    if len(sys.argv) > 1 and sys.argv[1].lower() == "yes":
        proceed = "yes"
    else:
        try:
            proceed = input("Do you want to proceed? (yes/no): ").lower()
        except EOFError:
            proceed = "yes"
            log("Non-interactive mode: proceeding automatically")

    if proceed == "yes":
        migrate()
    else:
        log("Cancelled")