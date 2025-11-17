-- Migration: Add primary_contact_name and website_url to contractors table
-- Run this in your PostgreSQL database

-- Add new columns
ALTER TABLE contractors ADD COLUMN IF NOT EXISTS primary_contact_name VARCHAR(255);
ALTER TABLE contractors ADD COLUMN IF NOT EXISTS website_url VARCHAR(500);
