#!/usr/bin/env python3
"""Add `pending_jurisdictions` table for jurisdiction approval workflow.

Run: python add_pending_jurisdictions.py

This script creates the pending_jurisdictions table to store state/city requests
that require admin approval before being added to user profiles.
It is idempotent (safe to run multiple times).
"""
import sys
from pathlib import Path
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

# Ensure src is importable like other project scripts
sys.path.insert(0, str(Path(__file__).parent / "src"))

print("[1] Starting script...")
print(f"[2] Python path: {sys.path[0]}")

try:
    print("[3] Attempting to import engine...")
    from app.core.database import engine
    print("[4] Engine imported successfully")
except Exception as e:
    print(f"[ERROR] Failed to import engine from src/app/core/database.py: {e}")
    sys.exit(2)


def table_exists(inspector, table_name):
    try:
        tables = inspector.get_table_names()
        return table_name in tables
    except Exception:
        return False


def main():
    print("[5] Starting main() function...")
    
    print("[6] Creating inspector...")
    inspector = inspect(engine)
    print("[7] Inspector created")
    
    print("[8] Getting table names...")
    tables = inspector.get_table_names()
    print(f"[9] Found {len(tables)} tables")

    try:
        # Create pending_jurisdictions table if not present
        print("[10] Checking if `pending_jurisdictions` table exists...")
        if "pending_jurisdictions" not in tables:
            print("[11] Table `pending_jurisdictions` not found, creating it...")
            print("[12] Opening database connection...")
            with engine.begin() as conn:
                print("[13] Connection opened, executing CREATE TABLE...")
                
                # Create table
                conn.execute(text("""
                    CREATE TABLE pending_jurisdictions (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        user_type VARCHAR(50) NOT NULL,
                        jurisdiction_type VARCHAR(50) NOT NULL,
                        jurisdiction_value VARCHAR(255) NOT NULL,
                        status VARCHAR(20) DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        reviewed_at TIMESTAMP,
                        reviewed_by INTEGER REFERENCES admin_users(id),
                        UNIQUE(user_id, jurisdiction_type, jurisdiction_value)
                    )
                """))
                print("[14] CREATE TABLE executed")
                
                # Create indexes
                print("[15] Creating indexes...")
                conn.execute(text("""
                    CREATE INDEX idx_pending_jurisdictions_status 
                    ON pending_jurisdictions(status)
                """))
                conn.execute(text("""
                    CREATE INDEX idx_pending_jurisdictions_user 
                    ON pending_jurisdictions(user_id)
                """))
                conn.execute(text("""
                    CREATE INDEX idx_pending_jurisdictions_type 
                    ON pending_jurisdictions(jurisdiction_type)
                """))
                print("[16] Indexes created")
                
            print("[17] Connection closed after CREATE")
            print("[18] Created table `pending_jurisdictions` with indexes.")
        else:
            print("[19] Table `pending_jurisdictions` already exists. No change made.")

        print("[20] Script completed successfully")
        return 0

    except SQLAlchemyError as e:
        print(f"[ERROR-DB] Database error while creating pending_jurisdictions: {e}")
        import traceback
        traceback.print_exc()
        return 2
    except Exception as e:
        print(f"[ERROR-GENERAL] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 3


if __name__ == "__main__":
    print("[0] Script invoked")
    exit_code = main()
    print(f"[FINAL] Exiting with code {exit_code}")
    sys.exit(exit_code)
