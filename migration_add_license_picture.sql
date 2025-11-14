-- Migration: Store license pictures in database instead of file system
-- Run this in your PostgreSQL database

-- Step 1: Add new columns for binary storage
ALTER TABLE contractors ADD COLUMN IF NOT EXISTS license_picture BYTEA;
ALTER TABLE contractors ADD COLUMN IF NOT EXISTS license_picture_filename VARCHAR(255);
ALTER TABLE contractors ADD COLUMN IF NOT EXISTS license_picture_content_type VARCHAR(50);

-- Step 2: Drop old URL column (after confirming data migration if needed)
ALTER TABLE contractors DROP COLUMN IF EXISTS license_picture_url;

-- Step 3: Also remove email_address if not done yet
ALTER TABLE contractors DROP COLUMN IF EXISTS email_address;

-- Step 4: Remove unused license columns
ALTER TABLE contractors DROP COLUMN IF EXISTS county_license;
ALTER TABLE contractors DROP COLUMN IF EXISTS occupational_license;
