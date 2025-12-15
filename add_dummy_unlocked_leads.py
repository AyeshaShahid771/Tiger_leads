"""
Script to add 3 dummy unlocked leads for user ID 67.
"""

import os
from datetime import datetime

import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def add_dummy_unlocked_leads():
    """Add 3 dummy unlocked leads for user 67"""
    try:
        # Connect to database
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        user_id = 67

        # First, check if user exists
        cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        if not cursor.fetchone():
            print(f"Error: User with ID {user_id} does not exist!")
            conn.close()
            return

        # Get first 3 jobs from the database
        cursor.execute("SELECT id FROM jobs ORDER BY id LIMIT 3")
        jobs = cursor.fetchall()

        if len(jobs) < 3:
            print(
                f"Error: Not enough jobs in database. Found {len(jobs)} jobs, need 3."
            )
            conn.close()
            return

        print(f"Adding 3 unlocked leads for user ID {user_id}...")

        for job in jobs:
            job_id = job[0]

            # Check if already unlocked
            cursor.execute(
                """
                SELECT id FROM unlocked_leads 
                WHERE user_id = %s AND job_id = %s
            """,
                (user_id, job_id),
            )

            if cursor.fetchone():
                print(
                    f"  - Job {job_id} already unlocked by user {user_id}, skipping..."
                )
                continue

            # Insert unlocked lead
            cursor.execute(
                """
                INSERT INTO unlocked_leads (user_id, job_id, credits_spent, notes, unlocked_at)
                VALUES (%s, %s, %s, %s, %s)
            """,
                (user_id, job_id, 1, f"Test note for job {job_id}", datetime.now()),
            )

            print(f"  ✓ Added unlocked lead for job {job_id}")

        conn.commit()
        print(f"\n✓ Successfully added unlocked leads for user {user_id}!")

        # Show summary
        cursor.execute(
            """
            SELECT COUNT(*) FROM unlocked_leads WHERE user_id = %s
        """,
            (user_id,),
        )
        total = cursor.fetchone()[0]
        print(f"Total unlocked leads for user {user_id}: {total}")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    add_dummy_unlocked_leads()
    add_dummy_unlocked_leads()
