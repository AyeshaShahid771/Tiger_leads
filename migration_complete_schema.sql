-- ============================================================================
-- Database Migration Script - Complete Schema
-- ============================================================================
-- This script creates all tables for the Tiger Leads application
-- Run this script to ensure all tables exist before starting the application
-- ============================================================================

-- Create users table
CREATE TABLE IF NOT EXISTS users (
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

-- Create index on email for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- ============================================================================
-- Create notifications table
-- ============================================================================
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    type VARCHAR(50),
    message VARCHAR,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_notifications_user
        FOREIGN KEY (user_id) 
        REFERENCES users(id) 
        ON DELETE CASCADE
);

-- Create index on user_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);

-- ============================================================================
-- Create password_resets table
-- ============================================================================
CREATE TABLE IF NOT EXISTS password_resets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_password_resets_user
        FOREIGN KEY (user_id) 
        REFERENCES users(id) 
        ON DELETE CASCADE
);

-- Create indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_password_resets_token ON password_resets(token);
CREATE INDEX IF NOT EXISTS idx_password_resets_user_id ON password_resets(user_id);

-- ============================================================================
-- Create contractors table
-- ============================================================================
CREATE TABLE IF NOT EXISTS contractors (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL,
    
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
        trade_categories VARCHAR(255),
        -- trade_specialities stores multiple specialities as a TEXT[] (PostgreSQL array)
        trade_specialities TEXT[],
    
    -- Step 4: Service Jurisdictions
    service_state VARCHAR(100),
    service_zip_code VARCHAR(20),
    
    -- Tracking fields
    registration_step INTEGER DEFAULT 0,
    is_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    
    CONSTRAINT fk_contractors_user
        FOREIGN KEY (user_id) 
        REFERENCES users(id) 
        ON DELETE CASCADE
);

-- Create index on user_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_contractors_user_id ON contractors(user_id);

-- ============================================================================
-- Create suppliers table
-- ============================================================================
CREATE TABLE IF NOT EXISTS suppliers (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL,
    
    -- Step 1: Basic Business Information
    company_name VARCHAR(255),
    primary_contact_name VARCHAR(255),
    phone_number VARCHAR(20),
    website_url VARCHAR(500),
    years_in_business INTEGER,
    business_type VARCHAR(100),
    
    -- Step 2: Service Area / Delivery Radius
    service_states TEXT,
    service_zipcode VARCHAR(20),
    onsite_delivery VARCHAR(10),
    delivery_lead_time VARCHAR(50),
    
    -- Step 3: Supplier Capabilities
    carries_inventory VARCHAR(10),
    offers_custom_orders VARCHAR(10),
    minimum_order_amount VARCHAR(100),
    accepts_urgent_requests VARCHAR(10),
    offers_credit_accounts VARCHAR(10),
    
    -- Step 4: Product Categories
    product_categories VARCHAR(255),
    -- product_types stores multiple subtypes as a TEXT[] (PostgreSQL array)
    product_types TEXT[],
    
    -- Tracking fields
    registration_step INTEGER DEFAULT 0,
    is_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    
    CONSTRAINT fk_suppliers_user
        FOREIGN KEY (user_id) 
        REFERENCES users(id) 
        ON DELETE CASCADE
);

-- Create index on user_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_suppliers_user_id ON suppliers(user_id);

-- ============================================================================
-- Verification Queries
-- ============================================================================
-- Uncomment these to verify tables were created successfully

-- List all tables
-- SELECT table_name FROM information_schema.tables 
-- WHERE table_schema = 'public' 
-- ORDER BY table_name;

-- Check table structure
-- SELECT column_name, data_type, is_nullable 
-- FROM information_schema.columns 
-- WHERE table_name = 'users';

-- Check foreign keys
-- SELECT
--     tc.table_name, 
--     kcu.column_name, 
--     ccu.table_name AS foreign_table_name,
--     ccu.column_name AS foreign_column_name 
-- FROM information_schema.table_constraints AS tc 
-- JOIN information_schema.key_column_usage AS kcu
--     ON tc.constraint_name = kcu.constraint_name
-- JOIN information_schema.constraint_column_usage AS ccu
--     ON ccu.constraint_name = tc.constraint_name
-- WHERE tc.constraint_type = 'FOREIGN KEY';

-- ============================================================================
-- End of Migration Script
-- ============================================================================
