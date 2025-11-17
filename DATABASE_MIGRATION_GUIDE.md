# Database Migration Guide

This guide explains how to initialize and manage the database schema for the Tiger Leads application.

## Overview

The Tiger Leads application requires the following database tables:

- **users** - User accounts and authentication
- **notifications** - User notifications
- **password_resets** - Password reset tokens
- **contractors** - Contractor registration profiles
- **suppliers** - Supplier registration profiles

## Migration Methods

You have **3 ways** to initialize your database:

### Method 1: Automatic (Recommended)

The application automatically creates all tables when it starts.

```bash
# Simply start your application
uvicorn src.app.main:app --reload
```

The `main.py` file includes automatic table creation on startup with detailed logging.

### Method 2: Python Script

Run the dedicated initialization script manually:

```bash
# Run the database initialization script
python init_database.py
```

This script will:

- ✓ Verify database connection
- ✓ Check existing tables
- ✓ Create missing tables
- ✓ Verify constraints and indexes
- ✓ Provide detailed logging

**Output Example:**

```
============================================================
DATABASE INITIALIZATION SCRIPT
============================================================
✓ Database connection verified
Starting database initialization...
Existing tables: ['users']
Creating tables from models...

============================================================
DATABASE INITIALIZATION SUMMARY
============================================================
✓ EXISTS    | users
✓ CREATED   | notifications
✓ CREATED   | password_resets
✓ CREATED   | contractors
✓ CREATED   | suppliers
============================================================

✓ Database initialization completed successfully!
```

### Method 3: SQL Script

If you prefer to use SQL directly:

```bash
# Using psql
psql -U postgres -d Tiger_leads -f migration_complete_schema.sql

# Or using any PostgreSQL client
# Connect to your database and run: migration_complete_schema.sql
```

## Database Schema

### Users Table

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR NOT NULL,
    email_verified BOOLEAN DEFAULT FALSE,
    verification_code VARCHAR(10),
    code_expires_at TIMESTAMP,
    role VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);
```

### Contractors Table

```sql
CREATE TABLE contractors (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- Step 1: Basic Business Information
    company_name VARCHAR(255),
    primary_contact_name VARCHAR(255),
    phone_number VARCHAR(20),
    website_url VARCHAR(500),
    business_address TEXT,
    business_type VARCHAR(100),
    years_in_business INTEGER,
    -- Step 2: License Information
    state_license_number VARCHAR(100),
    license_picture BYTEA,
    license_picture_filename VARCHAR(255),
    license_picture_content_type VARCHAR(50),
    license_expiration_date DATE,
    license_status VARCHAR(20),
    -- Step 3: Trade Information
    work_type VARCHAR(50),
    business_types TEXT,
    -- Step 4: Service Jurisdictions
    service_state VARCHAR(100),
    service_zip_code VARCHAR(20),
    -- Tracking
    registration_step INTEGER DEFAULT 0,
    is_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);
```

### Suppliers Table

```sql
CREATE TABLE suppliers (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- Step 1: Basic Business Information
    company_name VARCHAR(255),
    primary_contact_name VARCHAR(255),
    phone_number VARCHAR(20),
    website_url VARCHAR(500),
    years_in_business INTEGER,
    business_type VARCHAR(100),
    -- Step 2: Service Area
    service_states TEXT,
    service_zipcode VARCHAR(20),
    onsite_delivery VARCHAR(10),
    delivery_lead_time VARCHAR(50),
    -- Step 3: Capabilities
    carries_inventory VARCHAR(10),
    offers_custom_orders VARCHAR(10),
    minimum_order_amount VARCHAR(100),
    accepts_urgent_requests VARCHAR(10),
    offers_credit_accounts VARCHAR(10),
    -- Step 4: Product Categories
    product_categories TEXT,
    -- Tracking
    registration_step INTEGER DEFAULT 0,
    is_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);
```

## Verification

To verify all tables are created correctly:

### Using Python:

```python
from sqlalchemy import inspect
from src.app.core.database import engine

inspector = inspect(engine)
tables = inspector.get_table_names()
print("Tables:", tables)
```

### Using SQL:

```sql
-- List all tables
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

-- Check foreign key constraints
SELECT
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY';
```

## Troubleshooting

### Database Connection Issues

If you can't connect to the database:

1. Check your `.env` file or `database.py` for correct credentials
2. Ensure PostgreSQL is running
3. Verify the database exists:
   ```bash
   psql -U postgres -l
   ```

### Table Creation Fails

If tables don't get created:

1. Check database user permissions
2. Verify the user has CREATE TABLE permissions
3. Check logs for specific error messages

### Missing Tables

If some tables are missing:

1. Run `init_database.py` to see which tables are missing
2. Check for error messages in the logs
3. Manually create missing tables using the SQL script

## Database Configuration

Default database URL:

```
postgresql://postgres:Xb@qeJk3@localhost:5432/Tiger_leads
```

To change the database URL, set the `DATABASE_URL` environment variable:

```bash
export DATABASE_URL="postgresql://user:password@host:port/database"
```

## Migration Files

- **init_database.py** - Python script for database initialization
- **migration_complete_schema.sql** - SQL script with complete schema
- **src/app/main.py** - Automatic initialization on app startup

## Best Practices

1. **Always backup your database** before running migrations
2. **Test migrations** in a development environment first
3. **Use Method 1** (automatic) for development
4. **Use Method 2 or 3** for production deployments
5. **Keep migration files** in version control

## Support

If you encounter any issues:

1. Check application logs
2. Verify database connection
3. Ensure PostgreSQL version compatibility (9.5+)
4. Review error messages carefully
