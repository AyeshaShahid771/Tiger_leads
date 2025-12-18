import psycopg2
from psycopg2 import sql
import os

# Database connection parameters
DB_CONFIG = {
    "host": "postgres.railway.internal",
    "port": 5432,
    "database": "railway",
    "user": "postgres",
    "password": "gmnLGBlOsmGxWXLAtWvsZdnOpyzAIFKU"
}

def connect_to_db():
    """Establish and return a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("✅ Successfully connected to the database.")
        return conn
    except psycopg2.OperationalError as e:
        print("❌ Connection failed:", e)
        return None

if __name__ == "__main__":
    # Establish connection
    connection = connect_to_db()
    
    if connection:
        try:
            # Create a cursor
            cursor = connection.cursor()
            
            # Example: Get PostgreSQL version
            cursor.execute("SELECT version();")
            version = cursor.fetchone()
            print("🐘 PostgreSQL version:", version[0])

            # Example: List all tables in public schema
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public';
            """)
            tables = cursor.fetchall()
            print("\n🗃️ Tables in 'public' schema:")
            for table in tables:
                print(f"  - {table[0]}")

        except psycopg2.Error as e:
            print("❗ Database error:", e)
        finally:
            # Clean up
            cursor.close()
            connection.close()
            print("\n🔌 Connection closed.")