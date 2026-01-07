"""
Migration script to update supplier fields:

Step 1 changes:
1. Adds the business_address column
2. Drops the business_type column
3. Drops the years_in_business column
4. Drops the business_license_number column (moved to Step 3 as state_license_number)

Step 2 changes:
5. Drops the onsite_delivery column
6. Drops the delivery_lead_time column

Step 3 changes (Company Credentials - File Uploads):
7. Adds state_license_number, license_expiration_date, license_status columns
8. Adds license_picture, license_picture_filename, license_picture_content_type columns
9. Adds referrals, referrals_filename, referrals_content_type columns
10. Adds job_photos, job_photos_filename, job_photos_content_type columns
11. Drops carries_inventory column
12. Drops offers_custom_orders column
13. Drops minimum_order_amount column
14. Drops accepts_urgent_requests column
15. Drops offers_credit_accounts column

Step 4 changes (User Type):
16. Adds user_type column (array)
17. Drops product_categories column
18. Drops product_types column
"""

import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in environment variables")
    sys.exit(1)

engine = create_engine(DATABASE_URL)


def run_migration():
    """Execute the migration."""
    with engine.connect() as conn:
        print("=" * 60)
        print("Supplier Fields Migration")
        print("=" * 60)
        
        # Check if business_address column already exists
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='suppliers' AND column_name='business_address'
        """))
        
        if result.fetchone():
            print("✓ Column 'business_address' already exists in suppliers table")
        else:
            print("Adding 'business_address' column to suppliers table...")
            
            # Add business_address column
            conn.execute(text("""
                ALTER TABLE suppliers
                ADD COLUMN business_address TEXT
            """))
            conn.commit()
            
            print("✓ Column 'business_address' added successfully")
        
        # Check if business_license_number column exists before dropping (moved to Step 3 as state_license_number)
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='suppliers' AND column_name='business_license_number'
        """))
        
        if result.fetchone():
            print("Dropping 'business_license_number' column from suppliers table (moved to Step 3 as state_license_number)...")
            conn.execute(text("""
                ALTER TABLE suppliers
                DROP COLUMN business_license_number
            """))
            conn.commit()
            print("✓ Column 'business_license_number' dropped successfully")
        else:
            print("✓ Column 'business_license_number' already removed")
        
        # Check if business_type column exists before dropping
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='suppliers' AND column_name='business_type'
        """))
        
        if result.fetchone():
            print("Dropping 'business_type' column from suppliers table...")
            conn.execute(text("""
                ALTER TABLE suppliers
                DROP COLUMN business_type
            """))
            conn.commit()
            print("✓ Column 'business_type' dropped successfully")
        else:
            print("✓ Column 'business_type' already removed")
        
        # Check if years_in_business column exists before dropping
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='suppliers' AND column_name='years_in_business'
        """))
        
        if result.fetchone():
            print("Dropping 'years_in_business' column from suppliers table...")
            conn.execute(text("""
                ALTER TABLE suppliers
                DROP COLUMN years_in_business
            """))
            conn.commit()
            print("✓ Column 'years_in_business' dropped successfully")
        else:
            print("✓ Column 'years_in_business' already removed")
        
        # Check if onsite_delivery column exists before dropping
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='suppliers' AND column_name='onsite_delivery'
        """))
        
        if result.fetchone():
            print("Dropping 'onsite_delivery' column from suppliers table...")
            conn.execute(text("""
                ALTER TABLE suppliers
                DROP COLUMN onsite_delivery
            """))
            conn.commit()
            print("✓ Column 'onsite_delivery' dropped successfully")
        else:
            print("✓ Column 'onsite_delivery' already removed")
        
        # Check if delivery_lead_time column exists before dropping
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='suppliers' AND column_name='delivery_lead_time'
        """))
        
        if result.fetchone():
            print("Dropping 'delivery_lead_time' column from suppliers table...")
            conn.execute(text("""
                ALTER TABLE suppliers
                DROP COLUMN delivery_lead_time
            """))
            conn.commit()
            print("✓ Column 'delivery_lead_time' dropped successfully")
        else:
            print("✓ Column 'delivery_lead_time' already removed")
        
        # Step 3: Add Company Credentials file upload columns
        
        # Add state_license_number, license_expiration_date, license_status
        for col_name, col_type in [
            ('state_license_number', 'VARCHAR(100)'),
            ('license_expiration_date', 'DATE'),
            ('license_status', 'VARCHAR(20)')
        ]:
            result = conn.execute(text(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='suppliers' AND column_name='{col_name}'
            """))
            
            if result.fetchone():
                print(f"✓ Column '{col_name}' already exists in suppliers table")
            else:
                print(f"Adding '{col_name}' column to suppliers table...")
                conn.execute(text(f"""
                    ALTER TABLE suppliers
                    ADD COLUMN {col_name} {col_type}
                """))
                conn.commit()
                print(f"✓ Column '{col_name}' added successfully")
        
        # Add license_picture columns
        for col_name, col_type in [
            ('license_picture', 'BYTEA'),
            ('license_picture_filename', 'VARCHAR(255)'),
            ('license_picture_content_type', 'VARCHAR(50)')
        ]:
            result = conn.execute(text(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='suppliers' AND column_name='{col_name}'
            """))
            
            if result.fetchone():
                print(f"✓ Column '{col_name}' already exists in suppliers table")
            else:
                print(f"Adding '{col_name}' column to suppliers table...")
                conn.execute(text(f"""
                    ALTER TABLE suppliers
                    ADD COLUMN {col_name} {col_type}
                """))
                conn.commit()
                print(f"✓ Column '{col_name}' added successfully")
        
        # Add referrals columns
        for col_name, col_type in [
            ('referrals', 'BYTEA'),
            ('referrals_filename', 'VARCHAR(255)'),
            ('referrals_content_type', 'VARCHAR(50)')
        ]:
            result = conn.execute(text(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='suppliers' AND column_name='{col_name}'
            """))
            
            if result.fetchone():
                print(f"✓ Column '{col_name}' already exists in suppliers table")
            else:
                print(f"Adding '{col_name}' column to suppliers table...")
                conn.execute(text(f"""
                    ALTER TABLE suppliers
                    ADD COLUMN {col_name} {col_type}
                """))
                conn.commit()
                print(f"✓ Column '{col_name}' added successfully")
        
        # Add job_photos columns
        for col_name, col_type in [
            ('job_photos', 'BYTEA'),
            ('job_photos_filename', 'VARCHAR(255)'),
            ('job_photos_content_type', 'VARCHAR(50)')
        ]:
            result = conn.execute(text(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='suppliers' AND column_name='{col_name}'
            """))
            
            if result.fetchone():
                print(f"✓ Column '{col_name}' already exists in suppliers table")
            else:
                print(f"Adding '{col_name}' column to suppliers table...")
                conn.execute(text(f"""
                    ALTER TABLE suppliers
                    ADD COLUMN {col_name} {col_type}
                """))
                conn.commit()
                print(f"✓ Column '{col_name}' added successfully")
        
        # Drop old Step 3 capability columns
        old_step3_columns = [
            'carries_inventory',
            'offers_custom_orders',
            'minimum_order_amount',
            'accepts_urgent_requests',
            'offers_credit_accounts'
        ]
        
        for col_name in old_step3_columns:
            result = conn.execute(text(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='suppliers' AND column_name='{col_name}'
            """))
            
            if result.fetchone():
                print(f"Dropping '{col_name}' column from suppliers table...")
                conn.execute(text(f"""
                    ALTER TABLE suppliers
                    DROP COLUMN {col_name}
                """))
                conn.commit()
                print(f"✓ Column '{col_name}' dropped successfully")
            else:
                print(f"✓ Column '{col_name}' already removed")
        
        # Step 4: Add user_type and drop product columns
        
        # Add user_type column (array of strings)
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='suppliers' AND column_name='user_type'
        """))
        
        if result.fetchone():
            print("✓ Column 'user_type' already exists in suppliers table")
        else:
            print("Adding 'user_type' column to suppliers table...")
            conn.execute(text("""
                ALTER TABLE suppliers
                ADD COLUMN user_type TEXT[]
            """))
            conn.commit()
            print("✓ Column 'user_type' added successfully")
        
        # Drop old Step 4 product columns
        old_step4_columns = ['product_categories', 'product_types']
        
        for col_name in old_step4_columns:
            result = conn.execute(text(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='suppliers' AND column_name='{col_name}'
            """))
            
            if result.fetchone():
                print(f"Dropping '{col_name}' column from suppliers table...")
                conn.execute(text(f"""
                    ALTER TABLE suppliers
                    DROP COLUMN {col_name}
                """))
                conn.commit()
                print(f"✓ Column '{col_name}' dropped successfully")
            else:
                print(f"✓ Column '{col_name}' already removed")
        
        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
        
        # Verify final schema
        print("\nVerifying suppliers table schema:")
        result = conn.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name='suppliers' 
            AND column_name IN ('business_license_number', 'business_address', 'business_type', 'years_in_business', 'onsite_delivery', 'delivery_lead_time')
            ORDER BY column_name
        """))
        
        columns = result.fetchall()
        if columns:
            print("\nMigrated columns:")
            for col in columns:
                print(f"  - {col[0]}: {col[1]} - Nullable: {col[2]}")
        
        # Check which old columns remain (should be none)
        old_columns = [c for c in columns if c[0] in ['business_type', 'years_in_business', 'onsite_delivery', 'delivery_lead_time']]
        new_columns = [c for c in columns if c[0] in ['business_license_number', 'business_address']]
        
        if not old_columns and len(new_columns) == 2:
            print("\n✓ All old columns successfully removed")
            print("✓ New columns (business_license_number, business_address) successfully added")
        elif old_columns:
            print(f"\n⚠ Warning: Some old columns still exist: {[c[0] for c in old_columns]}")
        else:
            print(f"\n⚠ Warning: Expected columns may be missing")


if __name__ == "__main__":
    try:
        run_migration()
    except Exception as e:
        print(f"\n✗ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
