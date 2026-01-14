import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor(cursor_factory=RealDictCursor)

# Check Starter subscription
print("=== STARTER SUBSCRIPTION ===")
cursor.execute("SELECT * FROM subscriptions WHERE id = 2")
starter = cursor.fetchone()
if starter:
    for key, value in starter.items():
        print(f"{key}: {value}")
else:
    print("Starter subscription not found!")

print("\n=== USER 67 SUBSCRIBER RECORD ===")
cursor.execute("SELECT * FROM subscribers WHERE user_id = 67")
subscriber = cursor.fetchone()
if subscriber:
    for key, value in subscriber.items():
        print(f"{key}: {value}")
else:
    print("Subscriber not found!")

cursor.close()
conn.close()
