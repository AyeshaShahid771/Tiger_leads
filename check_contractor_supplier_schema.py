"""
Check schema for contractors and suppliers tables
"""
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

print("="*80)
print("CHECKING CONTRACTORS AND SUPPLIERS SCHEMA")
print("="*80)

# Check contractors table
print("\n" + "="*80)
print("CONTRACTORS TABLE SCHEMA")
print("="*80 + "\n")

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT 
            column_name,
            data_type,
            udt_name,
            is_nullable
        FROM information_schema.columns
        WHERE table_name = 'contractors'
        AND column_name IN ('user_type', 'state', 'country_city')
        ORDER BY ordinal_position
    """))
    
    for row in result.fetchall():
        col_name, data_type, udt_name, nullable = row
        print(f"{col_name:20} | {data_type:20} | udt: {udt_name:15} | nullable: {nullable}")

# Check suppliers table
print("\n" + "="*80)
print("SUPPLIERS TABLE SCHEMA")
print("="*80 + "\n")

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT 
            column_name,
            data_type,
            udt_name,
            is_nullable
        FROM information_schema.columns
        WHERE table_name = 'suppliers'
        AND column_name IN ('user_type', 'state', 'country_city')
        ORDER BY ordinal_position
    """))
    
    for row in result.fetchall():
        col_name, data_type, udt_name, nullable = row
        print(f"{col_name:20} | {data_type:20} | udt: {udt_name:15} | nullable: {nullable}")

# Check current data for contractors
print("\n" + "="*80)
print("CURRENT CONTRACTOR DATA (user_ids: 67, 80, 75, 88)")
print("="*80 + "\n")

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT user_id, user_type, state, country_city
        FROM contractors
        WHERE user_id IN (67, 80, 75, 88)
        ORDER BY user_id
    """))
    
    for row in result.fetchall():
        print(f"User {row[0]}: user_type={row[1]}, state={row[2]}, country_city={row[3]}")

# Check current data for suppliers
print("\n" + "="*80)
print("CURRENT SUPPLIER DATA (user_ids: 89, 76)")
print("="*80 + "\n")

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT user_id, user_type, state, country_city
        FROM suppliers
        WHERE user_id IN (89, 76)
        ORDER BY user_id
    """))
    
    for row in result.fetchall():
        print(f"User {row[0]}: user_type={row[1]}, state={row[2]}, country_city={row[3]}")

engine.dispose()
