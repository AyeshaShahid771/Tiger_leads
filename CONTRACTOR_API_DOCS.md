# Contractor Registration API Documentation

## Overview

This API provides a 4-step registration process for contractors. Each step requires authentication via JWT token and validates that the user has the "Contractor" role set.

## Prerequisites

1. User must be registered and email verified
2. User must set their role to "Contractor" using the `/auth/set-role` endpoint
3. Database must have the `contractors` table created

## Setup

### 1. Create the Contractors Table

Run the migration script to create the contractors table:

```bash
python create_contractors_table.py
```

### 2. Set User Role to Contractor

```http
POST /auth/set-role
Authorization: Bearer <your_access_token>
Content-Type: application/json

{
  "role": "Contractor"
}
```

## Registration Steps

### Step 1: Basic Business Information

**Endpoint:** `POST /contractor/step-1`

**Headers:**

```
Authorization: Bearer <your_access_token>
Content-Type: application/json
```

**Request Body:**

```json
{
  "company_name": "ACME Construction",
  "phone_number": "(555) 234-3455",
  "email_address": "abc@gmail.com",
  "business_address": "123 Main St., City, State",
  "business_type": "General Contractor",
  "years_in_business": 23
}
```

**Response:**

```json
{
  "message": "Basic business information saved successfully",
  "step_completed": 1,
  "total_steps": 4,
  "is_completed": false,
  "next_step": 2
}
```

---

### Step 2: License Information

**Endpoint:** `POST /contractor/step-2`

**Headers:**

```
Authorization: Bearer <your_access_token>
Content-Type: application/json
```

**Request Body:**

```json
{
  "state_license_number": "342342343242243243",
  "county_license": "CTY-12345",
  "occupational_license": "OCC-67890",
  "license_picture_url": "/uploads/license_123.jpg",
  "license_expiration_date": "2026-12-31",
  "license_status": "Active"
}
```

**Response:**

```json
{
  "message": "License information saved successfully",
  "step_completed": 2,
  "total_steps": 4,
  "is_completed": false,
  "next_step": 3
}
```

---

### Step 3: Trade Information

**Endpoint:** `POST /contractor/step-3`

**Headers:**

```
Authorization: Bearer <your_access_token>
Content-Type: application/json
```

**Request Body:**

```json
{
  "work_type": "Residential",
  "business_types": ["Plumbing", "Electrical", "Concrete", "Landscaping"]
}
```

**Allowed Business Types (Max 5):**

- Plumbing
- Electrical
- HVAC
- Roofing
- Painting
- Carpentry
- Concrete
- Landscaping
- Masonry
- Flooring
- Demolition
- Fencing

**Response:**

```json
{
  "message": "Trade information saved successfully",
  "step_completed": 3,
  "total_steps": 4,
  "is_completed": false,
  "next_step": 4
}
```

---

### Step 4: Service Jurisdictions (Final Step)

**Endpoint:** `POST /contractor/step-4`

**Headers:**

```
Authorization: Bearer <your_access_token>
Content-Type: application/json
```

**Request Body:**

```json
{
  "service_state": "New York",
  "service_zip_code": "LS1 1UR"
}
```

**Response:**

```json
{
  "message": "Contractor registration completed successfully! Your profile is now active.",
  "step_completed": 4,
  "total_steps": 4,
  "is_completed": true,
  "next_step": null
}
```

---

## Additional Endpoints

### Get Registration Status

**Endpoint:** `GET /contractor/registration-status`

**Headers:**

```
Authorization: Bearer <your_access_token>
```

**Response:**

```json
{
  "has_contractor_role": true,
  "profile_exists": true,
  "current_step": 2,
  "total_steps": 4,
  "is_completed": false,
  "next_step": 3,
  "message": "Please complete Step 3"
}
```

---

### Get Contractor Profile

**Endpoint:** `GET /contractor/profile`

**Headers:**

```
Authorization: Bearer <your_access_token>
```

**Response:**

```json
{
  "id": 1,
  "user_id": 5,
  "company_name": "ACME Construction",
  "phone_number": "(555) 234-3455",
  "email_address": "abc@gmail.com",
  "business_address": "123 Main St., City, State",
  "business_type": "General Contractor",
  "years_in_business": 23,
  "state_license_number": "342342343242243243",
  "county_license": "CTY-12345",
  "occupational_license": "OCC-67890",
  "license_picture_url": "/uploads/license_123.jpg",
  "license_expiration_date": "2026-12-31",
  "license_status": "Active",
  "work_type": "Residential",
  "business_types": "[\"Plumbing\", \"Electrical\", \"Concrete\", \"Landscaping\"]",
  "service_state": "New York",
  "service_zip_code": "LS1 1UR",
  "registration_step": 4,
  "is_completed": true
}
```

---

## Error Responses

### 403 Forbidden - No Contractor Role

```json
{
  "detail": "You must set your role to 'Contractor' before registering as a contractor"
}
```

### 400 Bad Request - Step Not Completed

```json
{
  "detail": "Please complete Step 1 before proceeding to Step 2"
}
```

### 400 Bad Request - Too Many Business Types

```json
{
  "detail": [
    {
      "loc": ["body", "business_types"],
      "msg": "You can select a maximum of 5 business types",
      "type": "value_error"
    }
  ]
}
```

---

## Flow Diagram

```
1. User Registration (/auth/signup)
   ↓
2. Email Verification (/auth/verify/{email})
   ↓
3. Login (/auth/login)
   ↓
4. Set Role to Contractor (/auth/set-role)
   ↓
5. Step 1: Basic Info (/contractor/step-1)
   ↓
6. Step 2: License Info (/contractor/step-2)
   ↓
7. Step 3: Trade Info (/contractor/step-3)
   ↓
8. Step 4: Jurisdictions (/contractor/step-4)
   ↓
9. Registration Complete ✓
```

---

## Notes

1. **Sequential Steps**: Each step must be completed in order. You cannot skip steps.
2. **Token Required**: All contractor endpoints require a valid JWT token in the Authorization header.
3. **Role Validation**: User must have role set to "Contractor" before accessing any contractor endpoints.
4. **Auto-Creation**: The contractor profile is automatically created when Step 1 is submitted.
5. **Tracking**: The system tracks which step you're on via the `registration_step` field.
6. **Business Types**: Stored as JSON string array, can be parsed on the frontend.

---

## Testing with cURL

### Complete Flow Example:

```bash
# 1. Set role to Contractor
curl -X POST http://localhost:8000/auth/set-role \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role": "Contractor"}'

# 2. Submit Step 1
curl -X POST http://localhost:8000/contractor/step-1 \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "ACME Construction",
    "phone_number": "(555) 234-3455",
    "email_address": "abc@gmail.com",
    "business_address": "123 Main St., City, State",
    "business_type": "General Contractor",
    "years_in_business": 23
  }'

# 3. Submit Step 2
curl -X POST http://localhost:8000/contractor/step-2 \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "state_license_number": "342342343242243243",
    "county_license": "CTY-12345",
    "occupational_license": "OCC-67890",
    "license_picture_url": "/uploads/license_123.jpg",
    "license_expiration_date": "2026-12-31",
    "license_status": "Active"
  }'

# 4. Submit Step 3
curl -X POST http://localhost:8000/contractor/step-3 \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "work_type": "Residential",
    "business_types": ["Plumbing", "Electrical", "Concrete", "Landscaping"]
  }'

# 5. Submit Step 4
curl -X POST http://localhost:8000/contractor/step-4 \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_state": "New York",
    "service_zip_code": "LS1 1UR"
  }'

# 6. Get Profile
curl -X GET http://localhost:8000/contractor/profile \
  -H "Authorization: Bearer YOUR_TOKEN"
```
