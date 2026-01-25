#!/usr/bin/env python3
"""Add `name` column to `admin_users` table.

Run: python add_admin_users_role.py
d uses the SQLAlchemy `engine`

"""
import sys
from pathlib import Path
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError


sys.path.insert(0, str(Path(__file__).parent / "src"))

print("[1] Starting script...")
print(f"[2] Python path: {sys.path[0]}")

try:
    print("[3] Attempting to import engine...")
    from src.app.core.database import engine
    print("[4] Engine imported successfully")
except Exception as e:
    print(f"[ERROR] Failed to import engine from src/app/core/database.py: {e}")
    sys.exit(2)


def column_exists(inspector, table, column_name):
    try:
        cols = [c["name"] for c in inspector.get_columns(table)]
    except Exception:
        return False
    return column_name in cols


def main():
    print("[5] Starting main() function...")
    
    print("[6] Creating inspector...")
    inspector = inspect(engine)
    print("[7] Inspector created")
    
    print("[8] Getting table names...")
    tables = inspector.get_table_names()
    print(f"[9] Found {len(tables)} tables")
    
    if "admin_users" not in tables:
        print("[10] Table `admin_users` does not exist. Nothing to do.")
        return 1
    
    print("[11] Table `admin_users` exists")
    
    # Get initial columns
    print("[12] Getting columns for admin_users...")
    cols = [c["name"] for c in inspector.get_columns("admin_users")]
    print(f"[13] Current columns: {cols}")

    try:
        # Add `name` column if not present
        print("[14] Checking if `name` column exists...")
        if "name" not in cols:
            print("[15] Column `name` not found, adding it...")
            print("[16] Opening database connection...")
            with engine.begin() as conn:
                print("[17] Connection opened, executing ADD COLUMN...")
                conn.execute(text("ALTER TABLE admin_users ADD COLUMN name VARCHAR(255)"))
                print("[18] ADD COLUMN executed")
            print("[19] Connection closed after ADD")
            print("[20] Added column `name` to `admin_users`.")
        else:
            print("[21] Column `name` already exists on `admin_users`. No change made.")

        print("[22] Script completed successfully")
        return 0

    except SQLAlchemyError as e:
        print(f"[ERROR-DB] Database error while modifying admin_users: {e}")
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