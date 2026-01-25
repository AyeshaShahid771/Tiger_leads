"""
Check supplier table schema in database
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'suppliers'
        ORDER BY ordinal_position
    """))
    
    print("Supplier table columns:")
    print("=" * 60)
    for row in result:
        print(f"{row.column_name:30} {row.data_type}")

engine.dispose()
