"""
Comprehensive database sequence fix script.
Fixes all table ID sequences to prevent duplicate key errors.

This script will:
1. Find all tables with ID sequences
2. Reset each sequence to the correct value based on max ID
3. Report results for each table
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in .env file")
    exit(1)

print(f"Connecting to database...")
print(f"Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'localhost'}")

engine = create_engine(DATABASE_URL)

# List of all tables with auto-incrementing IDs
# Format: (table_name, sequence_name)
TABLES_TO_FIX = [
    ("users", "users_id_seq"),
    ("user_invitations", "user_invitations_id_seq"),
    ("notifications", "notifications_id_seq"),
    ("password_resets", "password_resets_id_seq"),
    ("contractors", "contractors_id_seq"),
    ("suppliers", "suppliers_id_seq"),
    ("subscriptions", "subscriptions_id_seq"),
    ("subscribers", "subscribers_id_seq"),
    ("admin_users", "admin_users_id_seq"),
    ("jobs", "jobs_id_seq"),
    ("unlocked_leads", "unlocked_leads_id_seq"),
    ("not_interested_jobs", "not_interested_jobs_id_seq"),
    ("saved_jobs", "saved_jobs_id_seq"),
    ("temp_documents", "temp_documents_id_seq"),
    ("draft_jobs", "draft_jobs_id_seq"),
    ("pending_jurisdictions", "pending_jurisdictions_id_seq"),
]

try:
    with engine.connect() as conn:
        print("\n" + "=" * 70)
        print("FIXING ALL DATABASE SEQUENCES")
        print("=" * 70)
        
        results = []
        errors = []
        
        for table_name, sequence_name in TABLES_TO_FIX:
            try:
                # Get current max ID
                result = conn.execute(text(f"SELECT MAX(id) as max_id FROM {table_name}"))
                max_id = result.fetchone()[0] or 0
                
                # Reset sequence
                conn.execute(
                    text(f"SELECT setval('{sequence_name}', (SELECT COALESCE(MAX(id), 0) + 1 FROM {table_name}), false)")
                )
                conn.commit()
                
                results.append({
                    "table": table_name,
                    "max_id": max_id,
                    "next_id": max_id + 1,
                    "status": "✓ Fixed"
                })
                
                print(f"\n✓ {table_name:30} | Max ID: {max_id:6} | Next ID will be: {max_id + 1}")
                
            except Exception as e:
                error_msg = str(e)
                errors.append({
                    "table": table_name,
                    "error": error_msg
                })
                print(f"\n✗ {table_name:30} | Error: {error_msg[:50]}...")
        
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"\n✓ Successfully fixed: {len(results)} tables")
        if errors:
            print(f"✗ Errors encountered: {len(errors)} tables")
        
        if results:
            print("\n" + "-" * 70)
            print("Fixed Tables:")
            print("-" * 70)
            for r in results:
                print(f"  {r['table']:30} | Max ID: {r['max_id']:6} → Next: {r['next_id']}")
        
        if errors:
            print("\n" + "-" * 70)
            print("Errors:")
            print("-" * 70)
            for e in errors:
                print(f"  {e['table']:30} | {e['error'][:40]}...")
        
        print("\n" + "=" * 70)
        print("✓ Sequence fix complete!")
        print("=" * 70)
        print("\nAll sequences are now synchronized with their table data.")
        print("New records will be created with correct IDs.")

except Exception as e:
    print(f"\n✗ Fatal Error: {str(e)}")
    print("\nThis might mean:")
    print("- Database connection failed")
    print("- Permission issues")
    print("- Invalid database URL")

finally:
    engine.dispose()
