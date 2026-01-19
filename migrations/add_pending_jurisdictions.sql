-- Migration: Add pending_jurisdictions table
-- Purpose: Store jurisdiction requests (state/city) that require admin approval
-- Date: 2026-01-19

CREATE TABLE IF NOT EXISTS pending_jurisdictions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_type VARCHAR(50) NOT NULL,  -- 'Contractor' or 'Supplier'
    jurisdiction_type VARCHAR(50) NOT NULL,  -- 'state', 'country_city', 'service_states'
    jurisdiction_value VARCHAR(255) NOT NULL,  -- The actual value (e.g., 'California', 'Los Angeles')
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'approved', 'rejected'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP,
    reviewed_by INTEGER REFERENCES admin_users(id),
    UNIQUE(user_id, jurisdiction_type, jurisdiction_value)  -- Prevent duplicate requests
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_pending_jurisdictions_status ON pending_jurisdictions(status);
CREATE INDEX IF NOT EXISTS idx_pending_jurisdictions_user ON pending_jurisdictions(user_id);
CREATE INDEX IF NOT EXISTS idx_pending_jurisdictions_type ON pending_jurisdictions(jurisdiction_type);

-- Comments
COMMENT ON TABLE pending_jurisdictions IS 'Stores jurisdiction requests that require admin approval before being added to user profiles';
COMMENT ON COLUMN pending_jurisdictions.user_type IS 'Type of user making the request: Contractor or Supplier';
COMMENT ON COLUMN pending_jurisdictions.jurisdiction_type IS 'Type of jurisdiction: state, country_city, or service_states';
COMMENT ON COLUMN pending_jurisdictions.jurisdiction_value IS 'The actual jurisdiction value being requested';
COMMENT ON COLUMN pending_jurisdictions.status IS 'Approval status: pending, approved, or rejected';
