"""
Migration script to convert file upload columns from LargeBinary to JSON
for supporting multiple file uploads in Contractor and Supplier tables
"""
import os
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection (same as database.py)
password = quote_plus("Xb@qeJk3")
_raw_db = os.getenv(
    "DATABASE_URL", f"postgresql://postgres:{password}@localhost:5432/Tiger_leads"
)

# Tolerate misconfigured environment values
if isinstance(_raw_db, str):
    if _raw_db.startswith("DATABASE_URL="):
        _raw_db = _raw_db.split("=", 1)[1]
    if (_raw_db.startswith('"') and _raw_db.endswith('"')) or (
        _raw_db.startswith("'") and _raw_db.endswith("'")
    ):
        _raw_db = _raw_db[1:-1]

DATABASE_URL = _raw_db
engine = create_engine(DATABASE_URL)

def migrate_file_uploads():
    """Migrate file upload columns from LargeBinary to JSON"""
    
    with engine.connect() as conn:
        print("Starting migration: Converting file upload columns to JSON...")
        
        # Contractor table migration
        print("\n1. Migrating contractors table...")
        
        # Drop old columns
        conn.execute(text("""
            ALTER TABLE contractors 
            DROP COLUMN IF EXISTS license_picture_filename,
            DROP COLUMN IF EXISTS license_picture_content_type,
            DROP COLUMN IF EXISTS referrals_filename,
            DROP COLUMN IF EXISTS referrals_content_type,
            DROP COLUMN IF EXISTS job_photos_filename,
            DROP COLUMN IF EXISTS job_photos_content_type
        """))
        print("   ✓ Dropped old filename/content_type columns")
        
        # Change column types to JSON
        conn.execute(text("""
            ALTER TABLE contractors 
            ALTER COLUMN license_picture TYPE JSON USING 
                CASE 
                    WHEN license_picture IS NULL THEN NULL
                    ELSE '[]'::json 
                END,
            ALTER COLUMN referrals TYPE JSON USING 
                CASE 
                    WHEN referrals IS NULL THEN NULL
                    ELSE '[]'::json 
                END,
            ALTER COLUMN job_photos TYPE JSON USING 
                CASE 
                    WHEN job_photos IS NULL THEN NULL
                    ELSE '[]'::json 
                END
        """))
        print("   ✓ Converted license_picture, referrals, job_photos to JSON")
        
        # Supplier table migration
        print("\n2. Migrating suppliers table...")
        
        # Drop old columns
        conn.execute(text("""
            ALTER TABLE suppliers 
            DROP COLUMN IF EXISTS license_picture_filename,
            DROP COLUMN IF EXISTS license_picture_content_type,
            DROP COLUMN IF EXISTS referrals_filename,
            DROP COLUMN IF EXISTS referrals_content_type,
            DROP COLUMN IF EXISTS job_photos_filename,
            DROP COLUMN IF EXISTS job_photos_content_type
        """))
        print("   ✓ Dropped old filename/content_type columns")
        
        # Change column types to JSON
        conn.execute(text("""
            ALTER TABLE suppliers 
            ALTER COLUMN license_picture TYPE JSON USING 
                CASE 
                    WHEN license_picture IS NULL THEN NULL
                    ELSE '[]'::json 
                END,
            ALTER COLUMN referrals TYPE JSON USING 
                CASE 
                    WHEN referrals IS NULL THEN NULL
                    ELSE '[]'::json 
                END,
            ALTER COLUMN job_photos TYPE JSON USING 
                CASE 
                    WHEN job_photos IS NULL THEN NULL
                    ELSE '[]'::json 
                END
        """))
        print("   ✓ Converted license_picture, referrals, job_photos to JSON")
        
        conn.commit()
        
        print("\n✅ Migration completed successfully!")
        print("\nNote: Old binary file data has been cleared. Users will need to re-upload files.")

if __name__ == "__main__":
    print("="*70)
    print("File Upload Migration Script")
    print("="*70)
    print("\nThis script will:")
    print("  - Convert file upload columns from LargeBinary to JSON")
    print("  - Remove old filename and content_type columns")
    print("  - Enable support for multiple file uploads")
    print("\n⚠️  WARNING: Existing uploaded files will be cleared!")
    print("="*70)
    
    confirm = input("\nType 'MIGRATE' to proceed: ")
    
    if confirm == "MIGRATE":
        migrate_file_uploads()
    else:
        print("\n❌ Migration cancelled.")
