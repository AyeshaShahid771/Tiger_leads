-- Migration: Create suppliers table
-- Run this in your PostgreSQL database

CREATE TABLE IF NOT EXISTS suppliers (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    
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
    
    -- Step 4: Supplier Capabilities
    carries_inventory BOOLEAN,
    offers_custom_orders BOOLEAN,
    minimum_order_amount VARCHAR(100),
    accepts_urgent_requests BOOLEAN,
    offers_credit_accounts BOOLEAN,
    
    -- Step 5: Product Categories
    product_categories TEXT,
    
    -- Tracking fields
    registration_step INTEGER DEFAULT 0,
    is_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_suppliers_user_id ON suppliers(user_id);
