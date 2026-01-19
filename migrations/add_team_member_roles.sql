-- Migration: Add role columns for team member access control
-- Date: 2026-01-17

-- Add role column to user_invitations table
ALTER TABLE user_invitations 
ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'viewer' CHECK (role IN ('viewer', 'editor'));

-- Add team_role column to users table for sub-users
-- Note: This is different from the existing 'role' column which stores Contractor/Supplier
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS team_role VARCHAR(20) DEFAULT NULL CHECK (team_role IN ('viewer', 'editor', NULL));

-- Add comments to clarify the difference
COMMENT ON COLUMN users.role IS 'User type: Contractor or Supplier';
COMMENT ON COLUMN users.team_role IS 'Team member role: viewer or editor (only for sub-users with parent_user_id)';
COMMENT ON COLUMN user_invitations.role IS 'Team member role for invited user: viewer (read-only) or editor (full access)';
