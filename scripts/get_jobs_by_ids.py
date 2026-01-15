import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys
from datetime import datetime
import json

# =========================
# Database connection strings
# =========================
SOURCE_DB = "postgresql://postgres:MfxAqmdsoKRvATHsVcRinyMaFgwteIpT@ballast.proxy.rlwy.net:57684/railway"
TARGET_DB = "postgresql://postgres:jgscsvYlKTLKhjKqVonzKcPebUnHDkdr@centerbeam.proxy.rlwy.net:43363/railway"


# =========================
# Utility functions
# =========================
def log(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def get_connection(db_url):
    try:
        return psycopg2.connect(db_url)
    except Exception as e:
        log(f"Error connecting to database: {e}")
        sys.exit(1)


# =========================
# Schema helpers
# =========================
def get_all_tables(cursor):
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)
    return [row[0] for row in cursor.fetchall()]


def get_table_schema(cursor, table_name):
    """
    Generate CREATE TABLE without foreign keys
    FIXED: avoids integer(32,0) invalid syntax
    """
    cursor.execute(f"""
        SELECT
            'CREATE TABLE ' || quote_ident(table_name) || ' (' ||
            string_agg(
                quote_ident(column_name) || ' ' || column_type ||
                CASE WHEN is_nullable = 'NO' THEN ' NOT NULL' ELSE '' END ||
                CASE WHEN column_default IS NOT NULL THEN ' DEFAULT ' || column_default ELSE '' END,
                ', '
                ORDER BY ordinal_position
            ) || ');'
        FROM (
            SELECT
                c.column_name,
                c.is_nullable,
                c.column_default,
                c.ordinal_position,
                CASE
                    WHEN c.data_type = 'ARRAY' THEN
                        c.udt_name || '[]'
                    WHEN c.data_type = 'USER-DEFINED' THEN
                        c.udt_name
                    WHEN c.character_maximum_length IS NOT NULL THEN
                        c.data_type || '(' || c.character_maximum_length || ')'
                    WHEN c.data_type IN ('numeric', 'decimal') THEN
                        c.data_type || '(' || c.numeric_precision ||
                        CASE
                            WHEN c.numeric_scale IS NOT NULL THEN ',' || c.numeric_scale
                            ELSE ''
                        END || ')'
                    ELSE
                        c.data_type
                END AS column_type
            FROM information_schema.columns c
            WHERE c.table_schema = 'public'
              AND c.table_name = '{table_name}'
        ) cols;
    """)
    result = cursor.fetchone()
    return result[0] if result else None


def get_primary_keys(cursor, table_name):
    cursor.execute(f"""
        SELECT
            'ALTER TABLE ' || quote_ident(tc.table_name) ||
            ' ADD CONSTRAINT ' || quote_ident(tc.constraint_name) ||
            ' PRIMARY KEY (' ||
            string_agg(quote_ident(kcu.column_name), ', ' ORDER BY kcu.ordinal_position) ||
            ');'
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY'
          AND tc.table_schema = 'public'
          AND tc.table_name = '{table_name}'
        GROUP BY tc.table_name, tc.constraint_name;
    """)
    row = cursor.fetchone()
    return row[0] if row else None


def get_foreign_keys(cursor, table_name):
    cursor.execute(f"""
        SELECT
            'ALTER TABLE ' || quote_ident(tc.table_name) ||
            ' ADD CONSTRAINT ' || quote_ident(tc.constraint_name) ||
            ' FOREIGN KEY (' || string_agg(DISTINCT quote_ident(kcu.column_name), ', ') || ')' ||
            ' REFERENCES ' || quote_ident(ccu.table_name) ||
            ' (' || string_agg(DISTINCT quote_ident(ccu.column_name), ', ') || ')' ||
            CASE WHEN rc.update_rule <> 'NO ACTION' THEN ' ON UPDATE ' || rc.update_rule ELSE '' END ||
            CASE WHEN rc.delete_rule <> 'NO ACTION' THEN ' ON DELETE ' || rc.delete_rule ELSE '' END ||
            ';'
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
        JOIN information_schema.referential_constraints rc
          ON rc.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
          AND tc.table_name = '{table_name}'
        GROUP BY tc.table_name, tc.constraint_name, rc.update_rule, rc.delete_rule;
    """)
    return [row[0] for row in cursor.fetchall()]


def get_indexes(cursor, table_name):
    cursor.execute(f"""
        SELECT indexdef || ';'
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename = '{table_name}'
          AND indexdef NOT LIKE '%PRIMARY KEY%';
    """)
    return [row[0] for row in cursor.fetchall()]


def get_sequences(cursor):
    cursor.execute("""
        SELECT sequence_name, last_value
        FROM information_schema.sequences s
        JOIN pg_sequences ps
          ON s.sequence_name = ps.sequencename
        WHERE s.sequence_schema = 'public';
    """)
    return cursor.fetchall()


# =========================
# Migration logic
# =========================
def migrate_database():
    log("Starting database migration...")

    source_conn = get_connection(SOURCE_DB)
    target_conn = get_connection(TARGET_DB)
    target_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

    source_cursor = source_conn.cursor()
    target_cursor = target_conn.cursor()

    try:
        tables = get_all_tables(source_cursor)
        log(f"Found {len(tables)} tables: {', '.join(tables)}")

        # STEP 1: Create tables + PKs
        log("=== STEP 1: Creating tables ===")
        for table in tables:
            log(f"Creating table {table}")
            create_sql = get_table_schema(source_cursor, table)
            if create_sql:
                target_cursor.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE;')
                target_cursor.execute(create_sql)

            pk_sql = get_primary_keys(source_cursor, table)
            if pk_sql:
                target_cursor.execute(pk_sql)

        # STEP 2: Copy data
        log("=== STEP 2: Copying data ===")
        for table in tables:
            source_cursor.execute(f"""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = '{table}'
                ORDER BY ordinal_position;
            """)
            columns = [r[0] for r in source_cursor.fetchall()]
            if not columns:
                continue

            col_list = ', '.join(f'"{c}"' for c in columns)
            source_cursor.execute(f'SELECT {col_list} FROM "{table}";')
            rows = source_cursor.fetchall()

            if rows:
                placeholders = ', '.join(['%s'] * len(columns))
                insert_sql = f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders});'
                target_cursor.executemany(insert_sql, rows)
                log(f"Copied {len(rows)} rows into {table}")

        # STEP 3: Foreign keys
        log("=== STEP 3: Adding foreign keys ===")
        for table in tables:
            for fk_sql in get_foreign_keys(source_cursor, table):
                target_cursor.execute(fk_sql)

        # STEP 4: Indexes
        log("=== STEP 4: Creating indexes ===")
        for table in tables:
            for idx_sql in get_indexes(source_cursor, table):
                target_cursor.execute(idx_sql)

        # STEP 5: Sequences
        log("=== STEP 5: Updating sequences ===")
        for seq, val in get_sequences(source_cursor):
            target_cursor.execute(f"SELECT setval('{seq}', {val});")

        log("✅ Migration completed successfully")

    except Exception as e:
        log(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        source_cursor.close()
        target_cursor.close()
        source_conn.close()
        target_conn.close()
        log("Database connections closed")


# =========================
# Entry point
# =========================
if __name__ == "__main__":
    print("=" * 60)
    print("DATABASE MIGRATION SCRIPT")
    print("=" * 60)
    print(f"Source: {SOURCE_DB.split('@')[1]}")
    print(f"Target: {TARGET_DB.split('@')[1]}")
    print("=" * 60)

    # Quick-find mode: run with `--find-permits` to fetch jobs by permit numbers
    if "--find-permits" in sys.argv:
        permits = ["RES-NEW-26-000051", "RES-NEW-26-000054"]
        out_file = "jobs_617_618.json"
        log(f"Finding jobs in source DB for permits: {permits}")

        conn = get_connection(SOURCE_DB)
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT * FROM jobs WHERE permit_number = %s OR permit_number = %s",
                (permits[0], permits[1]),
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]

            with open(out_file, "w", encoding="utf-8") as fh:
                json.dump(rows, fh, default=str, indent=2)

            log(f"Wrote {len(rows)} row(s) to {out_file}")
        finally:
            cur.close()
            conn.close()

        sys.exit(0)

    response = input("Do you want to proceed? (yes/no): ")
    if response.lower() == "yes":
        migrate_database()
    else:
        log("Migration cancelled by user")
