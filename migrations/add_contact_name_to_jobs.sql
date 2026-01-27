-- Migration: Add contact_name column to jobs table
-- This adds a contact_name column to store the contact person's name for each job

-- Add contact_name column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name='jobs' AND column_name='contact_name'
    ) THEN
        ALTER TABLE jobs ADD COLUMN contact_name VARCHAR(255);
        RAISE NOTICE 'Added contact_name column to jobs table';
    ELSE
        RAISE NOTICE 'contact_name column already exists in jobs table';
    END IF;
END $$;

-- Verify the column was added
SELECT column_name, data_type, character_maximum_length
FROM information_schema.columns 
WHERE table_name='jobs' AND column_name='contact_name';
