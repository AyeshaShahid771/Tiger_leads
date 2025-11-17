# Supplier API Yes/No Field Fix - Summary

## Problem

The supplier registration API was converting user input of "yes" or "no" to boolean values (True/False) in the database for Step 3 fields:

- `carries_inventory`
- `offers_custom_orders`
- `accepts_urgent_requests`
- `offers_credit_accounts`

## Root Cause

These fields were defined as `bool` type in the Pydantic schema, causing automatic conversion from string to boolean.

## Solution

### 1. Schema Changes (`src/app/schemas/supplier.py`)

**Changed from:**

```python
class SupplierStep3(BaseModel):
    carries_inventory: bool
    offers_custom_orders: bool
    accepts_urgent_requests: bool
    offers_credit_accounts: bool
```

**Changed to:**

```python
class SupplierStep3(BaseModel):
    carries_inventory: str  # "yes" or "no"
    offers_custom_orders: str  # "yes" or "no"
    accepts_urgent_requests: str  # "yes" or "no"
    offers_credit_accounts: str  # "yes" or "no"
```

**Added validators** for each field to ensure only "yes" or "no" are accepted (case-insensitive).

### 2. Model Changes (`src/app/models/user.py`)

**Changed database column types from Boolean to String:**

```python
# Before
carries_inventory = Column(Boolean, nullable=True)
offers_custom_orders = Column(Boolean, nullable=True)
accepts_urgent_requests = Column(Boolean, nullable=True)
offers_credit_accounts = Column(Boolean, nullable=True)

# After
carries_inventory = Column(String(10), nullable=True)  # "yes" or "no"
offers_custom_orders = Column(String(10), nullable=True)  # "yes" or "no"
accepts_urgent_requests = Column(String(10), nullable=True)  # "yes" or "no"
offers_credit_accounts = Column(String(10), nullable=True)  # "yes" or "no"
```

### 3. Database Migration

Created `migration_update_supplier_yes_no_fields.sql` to:

- Convert existing Boolean columns to VARCHAR(10)
- Migrate existing data (TRUE → "yes", FALSE → "no")
- Preserve NULL values

## Implementation Steps

1. **Run the migration script:**

   ```bash
   # Connect to your database and run:
   psql -U your_username -d your_database -f migration_update_supplier_yes_no_fields.sql
   # OR for MySQL:
   mysql -u your_username -p your_database < migration_update_supplier_yes_no_fields.sql
   ```

2. **Restart your FastAPI server** to load the updated code

## Behavior After Fix

- Users can send "yes", "Yes", "YES" or "no", "No", "NO"
- The API will store it as lowercase: "yes" or "no"
- Database will store exactly "yes" or "no" (not True/False)
- Validators will reject any value other than "yes" or "no"

## Consistent with Step 2

This fix makes Step 3 fields consistent with Step 2's `onsite_delivery` field, which was already using the "yes"/"no" string approach.

## Files Modified

1. `src/app/schemas/supplier.py` - Updated Step 3 schema
2. `src/app/models/user.py` - Updated Supplier model
3. `migration_update_supplier_yes_no_fields.sql` - New migration file

## Testing

Test the Step 3 endpoint with:

```json
{
  "carries_inventory": "yes",
  "offers_custom_orders": "no",
  "minimum_order_amount": "$500",
  "accepts_urgent_requests": "yes",
  "offers_credit_accounts": "no"
}
```

The database should now store "yes" and "no" exactly as entered.
