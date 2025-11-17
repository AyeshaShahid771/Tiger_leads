"""
Script to check the current database schema for suppliers table
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect

# Load environment variables
load_dotenv()

# Get database URL
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in environment variables")
    exit(1)

# Create engine
engine = create_engine(DATABASE_URL)

# Get inspector
inspector = inspect(engine)

# Check if suppliers table exists
if "suppliers" not in inspector.get_table_names():
    print("❌ Suppliers table does not exist!")
    exit(1)

print("✅ Suppliers table found!\n")
print("=" * 80)
print("CURRENT SCHEMA FOR 'suppliers' TABLE:")
print("=" * 80)

# Get columns
columns = inspector.get_columns("suppliers")

# Print relevant columns
relevant_columns = [
    "onsite_delivery",
    "carries_inventory",
    "offers_custom_orders",
    "accepts_urgent_requests",
    "offers_credit_accounts",
]

print("\nYes/No Fields Status:")
print("-" * 80)
print(f"{'Column Name':<30} {'Type':<20} {'Nullable':<10}")
print("-" * 80)

for column in columns:
    if column["name"] in relevant_columns:
        col_type = str(column["type"])
        nullable = "Yes" if column["nullable"] else "No"
        print(f"{column['name']:<30} {col_type:<20} {nullable:<10}")

print("-" * 80)
print("\n📋 Expected Types:")
print("   - All should be: VARCHAR(10) or String")
print("\n⚠️  If any show as BOOLEAN, you need to run the migration!\n")
