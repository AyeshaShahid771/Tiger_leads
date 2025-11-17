-- Migration: Update Supplier Yes/No fields from Boolean to String
-- Date: 2025-11-17
-- Description: Change carries_inventory, offers_custom_orders, accepts_urgent_requests, 
--              offers_credit_accounts from BOOLEAN to VARCHAR(10) to store "yes" or "no"
--              Also clean up onsite_delivery to ensure it stores "yes"/"no" instead of "true"/"false"

-- Step 1: Add temporary columns with String type
ALTER TABLE suppliers ADD COLUMN carries_inventory_temp VARCHAR(10);
ALTER TABLE suppliers ADD COLUMN offers_custom_orders_temp VARCHAR(10);
ALTER TABLE suppliers ADD COLUMN accepts_urgent_requests_temp VARCHAR(10);
ALTER TABLE suppliers ADD COLUMN offers_credit_accounts_temp VARCHAR(10);
ALTER TABLE suppliers ADD COLUMN onsite_delivery_temp VARCHAR(10);

-- Step 2: Convert existing Boolean values to "yes"/"no" strings
UPDATE suppliers 
SET carries_inventory_temp = CASE 
    WHEN carries_inventory = TRUE THEN 'yes'
    WHEN carries_inventory = FALSE THEN 'no'
    ELSE NULL
END;

UPDATE suppliers 
SET offers_custom_orders_temp = CASE 
    WHEN offers_custom_orders = TRUE THEN 'yes'
    WHEN offers_custom_orders = FALSE THEN 'no'
    ELSE NULL
END;

UPDATE suppliers 
SET accepts_urgent_requests_temp = CASE 
    WHEN accepts_urgent_requests = TRUE THEN 'yes'
    WHEN accepts_urgent_requests = FALSE THEN 'no'
    ELSE NULL
END;

UPDATE suppliers 
SET offers_credit_accounts_temp = CASE 
    WHEN offers_credit_accounts = TRUE THEN 'yes'
    WHEN offers_credit_accounts = FALSE THEN 'no'
    ELSE NULL
END;

-- Step 2b: Clean up onsite_delivery - convert "true"/"false" to "yes"/"no"
UPDATE suppliers 
SET onsite_delivery_temp = CASE 
    WHEN LOWER(onsite_delivery) IN ('true', '1', 'yes') THEN 'yes'
    WHEN LOWER(onsite_delivery) IN ('false', '0', 'no') THEN 'no'
    ELSE NULL
END;

-- Step 3: Drop old columns
ALTER TABLE suppliers DROP COLUMN carries_inventory;
ALTER TABLE suppliers DROP COLUMN offers_custom_orders;
ALTER TABLE suppliers DROP COLUMN accepts_urgent_requests;
ALTER TABLE suppliers DROP COLUMN offers_credit_accounts;
ALTER TABLE suppliers DROP COLUMN onsite_delivery;

-- Step 4: Rename temporary columns to original names
ALTER TABLE suppliers RENAME COLUMN carries_inventory_temp TO carries_inventory;
ALTER TABLE suppliers RENAME COLUMN offers_custom_orders_temp TO offers_custom_orders;
ALTER TABLE suppliers RENAME COLUMN accepts_urgent_requests_temp TO accepts_urgent_requests;
ALTER TABLE suppliers RENAME COLUMN offers_credit_accounts_temp TO offers_credit_accounts;
ALTER TABLE suppliers RENAME COLUMN onsite_delivery_temp TO onsite_delivery;
