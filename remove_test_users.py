import os

import psycopg2

# Database connection parameters
conn_params = {
    "host": "34.60.129.6",
    "port": 5432,
    "database": "tigerleads",
    "user": "postgres",
    "password": "l1v*4V}OGv2&fME{",
    "sslmode": "disable",
}

print("Connecting to database...")
conn = psycopg2.connect(**conn_params)
cursor = conn.cursor()

print("Deleting test users...")
cursor.execute(
    "DELETE FROM users WHERE email IN ('test456@example.com', 'test789@example.com');"
)
deleted_count = cursor.rowcount
conn.commit()

print(f"Deleted {deleted_count} test user(s)")

print("\nVerifying deletion...")
cursor.execute("SELECT email FROM users WHERE email LIKE 'test%@example.com';")
remaining = cursor.fetchall()

if remaining:
    print(f"Found {len(remaining)} remaining test users:")
    for row in remaining:
        print(f"  - {row[0]}")
else:
    print("✓ All test users have been removed")

cursor.close()
conn.close()
print("\nDone!")
