"""
Script to delete all records from the jobs table.
WARNING: This will permanently delete all job/lead data!
"""

import os
from urllib.parse import quote_plus

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("Error: DATABASE_URL not found in .env file")
    exit(1)


def delete_all_jobs():
    """Delete all records from jobs table."""
    conn_params = DATABASE_URL.replace("postgresql://", "").split("@")
    user_pass = conn_params[0].split(":")
    host_db = conn_params[1].split("/")
    host_port = host_db[0].split(":")

    conn = psycopg2.connect(
        dbname=host_db[1],
        user=user_pass[0],
        password=user_pass[1],
        host=host_port[0],
        port=host_port[1] if len(host_port) > 1 else "5432",
    )

    cursor = conn.cursor()

    try:
        # First, check how many records exist
        cursor.execute("SELECT COUNT(*) FROM jobs;")
        count = cursor.fetchone()[0]

        print(f"Found {count} records in jobs table")

        if count == 0:
            print("Jobs table is already empty!")
            return

        # Show table structure
        cursor.execute(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'jobs'
            ORDER BY ordinal_position;
        """
        )

        print("\nJobs table structure:")
        print("-" * 60)
        for row in cursor.fetchall():
            col_name, data_type, nullable = row
            null_str = "NULL" if nullable == "YES" else "NOT NULL"
            print(f"  {col_name:30} {data_type:20} {null_str}")
        print("-" * 60)

        # Ask for confirmation
        print(
            f"\n⚠️  WARNING: This will DELETE ALL {count} records from the jobs table!"
        )
        confirmation = input("Type 'DELETE ALL' to confirm: ")

        if confirmation != "DELETE ALL":
            print("Deletion cancelled.")
            return

        # Delete all records
        print("\nDeleting all records...")
        cursor.execute("DELETE FROM jobs;")

        # Also delete related unlocked_leads records
        cursor.execute("SELECT COUNT(*) FROM unlocked_leads;")
        unlocked_count = cursor.fetchone()[0]

        if unlocked_count > 0:
            print(f"Also deleting {unlocked_count} related unlocked_leads records...")
            cursor.execute("DELETE FROM unlocked_leads;")

        conn.commit()

        # Verify deletion
        cursor.execute("SELECT COUNT(*) FROM jobs;")
        remaining = cursor.fetchone()[0]

        print(f"\n✅ Deletion completed!")
        print(f"   Jobs deleted: {count}")
        print(f"   Unlocked leads deleted: {unlocked_count}")
        print(f"   Remaining jobs: {remaining}")

        if remaining == 0:
            print("\n✅ Jobs table is now empty!")

    except Exception as e:
        conn.rollback()
        print(f"Error deleting jobs: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    delete_all_jobs()
