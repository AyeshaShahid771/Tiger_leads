import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor(cursor_factory=RealDictCursor)

# Check temp document
print("=== TEMP DOCUMENT RECORD ===")
cursor.execute("SELECT * FROM temp_documents WHERE temp_upload_id = 'TEMP-2A638FDCE5194046'")
temp_doc = cursor.fetchone()
if temp_doc:
    print(f"Found temp document:")
    for key, value in temp_doc.items():
        if key != 'documents':  # Skip large JSON field
            print(f"  {key}: {value}")
    if temp_doc.get('documents'):
        print(f"  documents: {len(temp_doc['documents'])} items")
else:
    print("Temp document not found!")

print("\n=== USER 67 INFO ===")
cursor.execute("SELECT id, email, role FROM users WHERE id = 67")
user = cursor.fetchone()
if user:
    for key, value in user.items():
        print(f"  {key}: {value}")
else:
    print("User 67 not found!")

cursor.close()
conn.close()
