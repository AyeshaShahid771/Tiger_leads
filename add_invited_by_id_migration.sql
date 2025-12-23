-- Migration: add invited_by_id to users
-- Run this against your database to add the new column. Adjust SQL for your DB dialect if needed.

ALTER TABLE users
ADD COLUMN invited_by_id INTEGER;

-- If using Postgres and want FK constraint:
-- ALTER TABLE users
-- ADD CONSTRAINT fk_invited_by FOREIGN KEY (invited_by_id) REFERENCES users(id) ON DELETE SET NULL;

-- Add index for performance
CREATE INDEX IF NOT EXISTS ix_users_invited_by_id ON users (invited_by_id);
