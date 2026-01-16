-- Migration: Add name, phone_number, and user_type to user_invitations table
-- Date: 2026-01-16

-- Add new columns to user_invitations table
ALTER TABLE user_invitations 
ADD COLUMN IF NOT EXISTS invited_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS invited_phone_number VARCHAR(20),
ADD COLUMN IF NOT EXISTS invited_user_type TEXT[];

-- Add comments to document the columns
COMMENT ON COLUMN user_invitations.invited_name IS 'Name of the invited user';
COMMENT ON COLUMN user_invitations.invited_phone_number IS 'Phone number of the invited user';
COMMENT ON COLUMN user_invitations.invited_user_type IS 'Array of user types (trades/business types) for the invited user';
