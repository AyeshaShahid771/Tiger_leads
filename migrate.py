"""
Standalone Data + FK Migration Script
Run this AFTER tables are created (your Phase 1 succeeded).
"""
import psycopg2
from psycopg2 import sql
import sys
from datetime import datetime

# ✅ Your DB URLs
SOURCE_DB = "postgresql://postgres:gmnLGBlOsmGxWXLAtWvsZdnOpyzAIFKU@interchange.proxy.rlwy.net:45895/railway"
DEST_DB = "postgresql://postgres:MfxAqmdsoKRvATHsVcRinyMaFgwteIpT@ballast.proxy.rlwy.net:57684/railway"

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def connect_db(connection_string, name):
    try:
        conn = psycopg2.connect(
            connection_string,
            connect_timeout=10,
            options="-c statement_timeout=300000"  # 5 min per query
        )
        log(f"✅ Connected to {name} DB")
        return conn
    except Exception as e:
        log(f"❌ Failed to connect to {name}: {e}")
        sys.exit(1)

def get_all_tables(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' 
            ORDER BY tablename;
        """)
        return [r[0] for r in cur.fetchall()]

def copy_table_batched(src_conn, dest_conn, table_name, batch_size=1):  # batch_size=1 for per-row
    try:
        # Get columns
        with src_conn.cursor() as meta_cur:
            meta_cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = %s AND table_schema = 'public'
                ORDER BY ordinal_position;
            """, (table_name,))
            cols = [r[0] for r in meta_cur.fetchall()]
        if not cols:
            log(f"  ⚠️ No columns in '{table_name}'")
            return 0

        # Get count
        with src_conn.cursor() as count_cur:
            count_cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table_name)))
            total = count_cur.fetchone()[0]
        if total == 0:
            log(f"  ⚠️ '{table_name}' is empty")
            return 0

        log(f"  📊 Total rows: {total:,}")

        # Fetch all rows (safe for small tables)
        with src_conn.cursor() as src_cur:
            src_cur.execute(sql.SQL("SELECT {} FROM {}").format(
                sql.SQL(', ').join(map(sql.Identifier, cols)),
                sql.Identifier(table_name)
            ))
            all_rows = src_cur.fetchall()

        # Prepare INSERT
        insert = sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT DO NOTHING").format(
            sql.Identifier(table_name),
            sql.SQL(', ').join(map(sql.Identifier, cols)),
            sql.SQL(', ').join(sql.Placeholder() * len(cols))
        )

        # ✅ Insert one row at a time + log each
        copied = 0
        for i, row in enumerate(all_rows, start=1):
            try:
                with dest_conn.cursor() as dest_cur:
                    dest_cur.execute(insert, row)
                    dest_conn.commit()
                log(f"    ➕ Row {i}/{total:,} inserted")  # 🔹 PER-ROW LOG
                copied += 1
            except Exception as e:
                log(f"    ❌ Failed to insert row {i}: {e}")
                # Continue with next row

        log(f"  ✅ Copied {copied:,} rows to '{table_name}'")
        return copied

    except Exception as e:
        log(f"  ❌ Failed to copy '{table_name}': {e}")
        return 0

def get_foreign_keys(conn, table_name):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                tc.constraint_name,
                kcu.column_name,
                ccu.table_name,
                ccu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = %s
                AND tc.table_schema = 'public'
            ORDER BY tc.constraint_name;
        """, (table_name,))
        fks = {}
        for name, local_col, ref_table, ref_col in cur.fetchall():
            fks.setdefault(name, {'cols': [], 'ref_table': ref_table, 'ref_cols': []})
            fks[name]['cols'].append(local_col)
            fks[name]['ref_cols'].append(ref_col)
        return fks

def add_foreign_keys(dest_conn, table_name, fks):
    try:
        with dest_conn.cursor() as cur:
            for name, info in fks.items():
                local_cols = ', '.join(f'"{c}"' for c in info['cols'])
                ref_cols = ', '.join(f'"{c}"' for c in info['ref_cols'])
                stmt = f'ALTER TABLE "{table_name}" ADD CONSTRAINT "{name}" ' \
                       f'FOREIGN KEY ({local_cols}) REFERENCES "{info["ref_table"]}"({ref_cols});'
                cur.execute(stmt)
                dest_conn.commit()
                log(f"    ✅ Added FK: {name}")
    except Exception as e:
        log(f"    ⚠️ Failed to add FKs for '{table_name}': {e}")

# ======================
# MAIN EXECUTION
# ======================
if __name__ == "__main__":
    log("=" * 60)
    log("🚀 STARTING DATA & FK MIGRATION (tables already exist)")
    log("=" * 60)

    src_conn = None
    dest_conn = None
    try:
        src_conn = connect_db(SOURCE_DB, "source")
        dest_conn = connect_db(DEST_DB, "destination")

        tables = get_all_tables(src_conn)
        log(f"📋 Found {len(tables)} tables: {', '.join(tables)}")

        # PHASE 1: Data copy (with per-row logging)
        log("\n" + "="*60)
        log("📦 COPYING DATA (1 row at a time)")
        log("="*60)
        total_rows = 0
        for table in tables:
            log(f"\n➡️  Copying: {table}")
            rows = copy_table_batched(src_conn, dest_conn, table)
            total_rows += rows

        # PHASE 2: FKs
        log("\n" + "="*60)
        log("🔗 ADDING FOREIGN KEY CONSTRAINTS")
        log("="*60)
        for table in tables:
            log(f"\n🔗 Processing FKs for: {table}")
            fks = get_foreign_keys(src_conn, table)
            if fks:
                add_foreign_keys(dest_conn, table, fks)
            else:
                log("    (no FKs found)")

        log("\n" + "="*60)
        log("🎉 SUCCESS!")
        log(f"✅ Total rows migrated: {total_rows:,}")
        log("="*60)

    except Exception as e:
        log(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if src_conn:
            src_conn.close()
        if dest_conn:
            dest_conn.close()
        log("\n🔌 Connections closed")