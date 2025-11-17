# 🚀 Quick Start Guide - Contractor Registration

## Step-by-Step Setup

### 1️⃣ Create the Database Table

```bash
python create_contractors_table.py
```

✅ This creates the `contractors` table with all required fields

---

### 2️⃣ Start the Server (if not already running)

```bash
# Windows (cmd)
uvicorn src.app.main:app --reload

# Or if using virtual environment
Tiger_leads\Scripts\activate
uvicorn src.app.main:app --reload
```

---

### 3️⃣ Complete User Flow

#### A. Register & Verify Email

1. **Sign Up:** `POST /auth/signup`
2. **Verify Email:** `POST /auth/verify/{email}`
3. **Login:** `POST /auth/login` → Get access token

#### B. Set Role to Contractor

```http
POST /auth/set-role
Authorization: Bearer YOUR_ACCESS_TOKEN
Content-Type: application/json

{
  "role": "Contractor"
}
```

#### C. Complete 4-Step Contractor Registration

**Step 1 - Basic Business Info:**

```http
POST /contractor/step-1
Authorization: Bearer YOUR_ACCESS_TOKEN

{
  "company_name": "ACME Construction",
  "phone_number": "(555) 234-3455",
  "email_address": "abc@gmail.com",
  "business_address": "123 Main St., City, State",
  "business_type": "General Contractor",
  "years_in_business": 23
}
```

**Step 2 - License Info:**

```http
POST /contractor/step-2
Authorization: Bearer YOUR_ACCESS_TOKEN

{
  "state_license_number": "342342343242243243",
  "county_license": "CTY-12345",
  "occupational_license": "OCC-67890",
  "license_picture_url": "/uploads/license.jpg",
  "license_expiration_date": "2026-12-31",
  "license_status": "Active"
}
```

**Step 3 - Trade Info (Max 5 Types):**

```http
POST /contractor/step-3
Authorization: Bearer YOUR_ACCESS_TOKEN

{
  "work_type": "Residential",
  "business_types": ["Plumbing", "Electrical", "Concrete", "Landscaping"]
}
```

**Step 4 - Service Jurisdictions:**

```http
POST /contractor/step-4
Authorization: Bearer YOUR_ACCESS_TOKEN

{
  "service_state": "New York",
  "service_zip_code": "LS1 1UR"
}
```

---

## ✅ Verify Registration

### Check Status:

```http
GET /contractor/registration-status
Authorization: Bearer YOUR_ACCESS_TOKEN
```

### Get Profile:

```http
GET /contractor/profile
Authorization: Bearer YOUR_ACCESS_TOKEN
```

---

## 📋 Important Notes

1. **Sequential Steps:** Must complete steps in order (1→2→3→4)
2. **Authentication:** All endpoints require JWT token
3. **Role Required:** User must set role to "Contractor" first
4. **Business Types:** Max 5 selections in Step 3
5. **Auto-Creation:** Contractor profile auto-created on Step 1

---

## 🎯 Available Business Types

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

---

## 🔧 Troubleshooting

### "Contractor role required" error

→ Set your role to "Contractor" using `/auth/set-role`

### "Please complete Step X first" error

→ Complete previous steps in order

### "You can select a maximum of 5 business types"

→ Reduce business_types array to max 5 items

### Database connection errors

→ Check your `.env` file has correct DATABASE_URL

---

## 📖 Full Documentation

See **CONTRACTOR_API_DOCS.md** for complete API documentation with all examples and error codes.
