"""
Migration script to convert location fields to arrays in contractors and suppliers tables.

Changes:
1. contractors.state: String -> ARRAY(String)
2. contractors.country_city: String -> ARRAY(String)
3. suppliers.service_states: Text (JSON) -> ARRAY(String)
4. suppliers.country_city: String -> ARRAY(String)

Run this script once to migrate your database.
"""

import json
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment variables")
    exit(1)

engine = create_engine(DATABASE_URL)

print("🔄 Starting migration: Converting location fields to arrays...")
print("=" * 70)

try:
    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()

        try:
            print("\n1️⃣ Checking contractors table...")

            # Check if columns are already arrays
            result = conn.execute(
                text(
                    """
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_name = 'contractors' AND column_name = 'state'
            """
                )
            )
            current_type = result.scalar()

            if current_type == "ARRAY":
                print("   ℹ️  Contractors columns are already ARRAY type, skipping...")
            else:
                print("   - Migrating contractors table...")
                print("   - Adding temporary array columns...")
                conn.execute(
                    text(
                        "ALTER TABLE contractors ADD COLUMN IF NOT EXISTS state_temp TEXT[]"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE contractors ADD COLUMN IF NOT EXISTS country_city_temp TEXT[]"
                    )
                )

                # Convert existing data to arrays (handle TEXT or JSON strings)
                print("   - Converting existing data to arrays...")

                # Get all contractors and convert individually
                contractors = conn.execute(
                    text("SELECT id, state, country_city FROM contractors")
                ).fetchall()

                for contractor_id, state_val, city_val in contractors:
                    state_array = None
                    city_array = None

                    # Parse state
                    if state_val:
                        try:
                            parsed = json.loads(state_val)
                            state_array = (
                                parsed if isinstance(parsed, list) else [str(parsed)]
                            )
                        except:
                            state_array = [state_val]

                    # Parse country_city
                    if city_val:
                        try:
                            parsed = json.loads(city_val)
                            city_array = (
                                parsed if isinstance(parsed, list) else [str(parsed)]
                            )
                        except:
                            city_array = [city_val]

                    if state_array:
                        conn.execute(
                            text(
                                "UPDATE contractors SET state_temp = :val WHERE id = :id"
                            ),
                            {"val": state_array, "id": contractor_id},
                        )
                    if city_array:
                        conn.execute(
                            text(
                                "UPDATE contractors SET country_city_temp = :val WHERE id = :id"
                            ),
                            {"val": city_array, "id": contractor_id},
                        )

                # Drop old columns and rename new ones
                print("   - Replacing old columns with new array columns...")
                conn.execute(text("ALTER TABLE contractors DROP COLUMN state"))
                conn.execute(text("ALTER TABLE contractors DROP COLUMN country_city"))
                conn.execute(
                    text("ALTER TABLE contractors RENAME COLUMN state_temp TO state")
                )
                conn.execute(
                    text(
                        "ALTER TABLE contractors RENAME COLUMN country_city_temp TO country_city"
                    )
                )

                print("   ✅ Contractors table migrated successfully")

            print("\n2️⃣ Checking suppliers table...")

            # Check if columns are already arrays
            result = conn.execute(
                text(
                    """
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_name = 'suppliers' AND column_name = 'service_states'
            """
                )
            )
            current_type = result.scalar()

            if current_type == "ARRAY":
                print("   ℹ️  Suppliers columns are already ARRAY type, skipping...")
            else:
                print("   - Migrating suppliers table...")
                print("   - Adding temporary array columns...")
                conn.execute(
                    text(
                        "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS service_states_temp TEXT[]"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS country_city_temp TEXT[]"
                    )
                )

                # Get all suppliers to convert JSON strings to arrays
                print("   - Converting JSON strings to arrays...")
                result = conn.execute(
                    text("SELECT id, service_states, country_city FROM suppliers")
                )
                suppliers = result.fetchall()

                for supplier in suppliers:
                    supplier_id, service_states_json, country_city_str = supplier

                    # Parse service_states JSON
                    service_states_array = None
                    if service_states_json:
                        try:
                            parsed = json.loads(service_states_json)
                            if isinstance(parsed, list):
                                service_states_array = parsed
                        except:
                            # If not valid JSON, treat as single string
                            service_states_array = [service_states_json]

                    # Convert country_city to array
                    country_city_array = None
                    if country_city_str:
                        try:
                            parsed = json.loads(country_city_str)
                            country_city_array = (
                                parsed if isinstance(parsed, list) else [str(parsed)]
                            )
                        except:
                            country_city_array = [country_city_str]

                    # Update with arrays
                    if service_states_array:
                        conn.execute(
                            text(
                                "UPDATE suppliers SET service_states_temp = :states WHERE id = :id"
                            ),
                            {"states": service_states_array, "id": supplier_id},
                        )

                    if country_city_array:
                        conn.execute(
                            text(
                                "UPDATE suppliers SET country_city_temp = :cities WHERE id = :id"
                            ),
                            {"cities": country_city_array, "id": supplier_id},
                        )

                # Drop old columns and rename new ones
                print("   - Replacing old columns with new array columns...")
                conn.execute(text("ALTER TABLE suppliers DROP COLUMN service_states"))
                conn.execute(text("ALTER TABLE suppliers DROP COLUMN country_city"))
                conn.execute(
                    text(
                        "ALTER TABLE suppliers RENAME COLUMN service_states_temp TO service_states"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE suppliers RENAME COLUMN country_city_temp TO country_city"
                    )
                )

                print("   ✅ Suppliers table migrated successfully")

            # Commit transaction
            trans.commit()

            print("\n" + "=" * 70)
            print("✅ Migration completed successfully!")
            print("\nSummary:")
            print("  • contractors.state: String → ARRAY(String)")
            print("  • contractors.country_city: String → ARRAY(String)")
            print("  • suppliers.service_states: Text (JSON) → ARRAY(String)")
            print("  • suppliers.country_city: String → ARRAY(String)")
            print(
                "\n⚠️  Note: Existing single values were converted to single-element arrays"
            )
            print("=" * 70)

        except Exception as e:
            trans.rollback()
            print(f"\n❌ Migration failed: {str(e)}")
            print("   Transaction rolled back. No changes were made.")
            raise

except Exception as e:
    print(f"\n❌ Database connection error: {str(e)}")
    exit(1)
    exit(1)
