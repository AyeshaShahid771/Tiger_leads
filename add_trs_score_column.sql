-- Migration: Add trs_score column to jobs table
-- Date: 2025-11-28
-- Description: Adds TRS (Total Relevance Score) column to store calculated lead quality score

-- Add the trs_score column
ALTER TABLE jobs 
ADD COLUMN trs_score INTEGER;

-- Add comment to document the column
COMMENT ON COLUMN jobs.trs_score IS 'Total Relevance Score (0-100): Average of project value score, stage score, and contact score';

-- Optional: Create index for filtering/sorting by TRS score
CREATE INDEX idx_jobs_trs_score ON jobs(trs_score);

-- Verify the column was added
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'jobs' AND column_name = 'trs_score';
