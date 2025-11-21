# Subscription and Jobs System - API Documentation

This document describes the new subscription, jobs, and dashboard APIs added to the TigerLeads system.

## New Database Tables

### 1. Subscriptions Table
Stores the subscription plan tiers.

**Fields:**
- `id`: Primary key
- `name`: Starter, Pro, or Elite
- `price`: Monthly price (e.g., "$89.99/month")
- `tokens`: Number of credits (100, 300, or 1000)

### 2. Subscribers Table
Tracks user subscriptions and credit balance.

**Fields:**
- `id`: Primary key
- `user_id`: Foreign key to users table (unique)
- `subscription_id`: Foreign key to subscriptions table
- `current_credits`: Available credits
- `total_spending`: Total credits spent
- `subscription_start_date`: When subscription started
- `subscription_renew_date`: Next renewal date
- `is_active`: Subscription status

### 3. Jobs Table
Stores all available leads/jobs.

**Fields:**
- `id`: Primary key
- `permit_record_number`: Permit/Record number
- `date`: Job date
- `permit_type`: Type of permit
- `project_description`: Description of project
- `job_address`: Job location address
- `job_cost`: Project value/cost
- `permit_status`: Status of permit
- `email`: Contact email (hidden until unlocked)
- `phone_number`: Contact phone (hidden until unlocked)
- `country`: Country
- `city`: City (indexed for filtering)
- `state`: State (indexed for filtering)
- `work_type`: Type of work (indexed for filtering)

### 4. Unlocked Leads Table
Tracks which users have unlocked which jobs.

**Fields:**
- `id`: Primary key
- `user_id`: Foreign key to users table
- `job_id`: Foreign key to jobs table
- `credits_spent`: Credits used to unlock
- `unlocked_at`: Timestamp of unlock

## API Endpoints

### Subscription Endpoints

#### GET `/subscription/plans`
Get all available subscription plans.

**Response:**
```json
[
  {
    "id": 1,
    "name": "Starter",
    "price": "$89.99/month",
    "tokens": 100
  },
  {
    "id": 2,
    "name": "Pro",
    "price": "$199.99/month",
    "tokens": 300
  },
  {
    "id": 3,
    "name": "Elite",
    "price": "$499.99/month",
    "tokens": 1000
  }
]
```

#### POST `/subscription/subscribe`
Subscribe to a plan.

**Request:**
```json
{
  "subscription_id": 2
}
```

**Response:**
```json
{
  "id": 1,
  "user_id": 123,
  "subscription_id": 2,
  "current_credits": 300,
  "total_spending": 0,
  "subscription_start_date": "2025-11-20T10:00:00",
  "subscription_renew_date": "2025-12-20T10:00:00",
  "is_active": true
}
```

#### GET `/subscription/my-subscription`
Get current user's subscription details.

**Response:** Same as subscribe response

#### GET `/subscription/wallet`
Get user's wallet information including credits and spending history.

**Response:**
```json
{
  "current_credits": 285,
  "total_spending": 15,
  "subscription": "Pro",
  "subscription_renew_date": "2025-12-20T10:00:00",
  "spending_history": [
    {
      "job_id": 456,
      "credits_spent": 1,
      "unlocked_at": "2025-11-19T15:30:00"
    }
  ]
}
```

### Jobs Endpoints

#### POST `/jobs/upload-leads`
Bulk upload leads/jobs from CSV or Excel file.

**Request:**
- Content-Type: multipart/form-data
- Body: file (CSV or Excel)

**Expected CSV/Excel columns:**
- `permit_record_number` - Permit or record number
- `date` - Job date (YYYY-MM-DD format)
- `permit_type` - Type of permit
- `project_description` - Project description
- `job_address` - Job address
- `job_cost` - Project value/cost
- `permit_status` - Permit status
- `email` - Contact email
- `phone_number` - Contact phone
- `country` - Country
- `city` - City
- `state` - State
- `work_type` - Type of work (Residential/Commercial/Industrial)
- `credit_cost` - Credits required to unlock (optional, defaults to 1)
- `category` - Lead category (optional)

**Response:**
```json
{
  "total_rows": 100,
  "successful": 98,
  "failed": 2,
  "errors": [
    "Row 5: Invalid date format",
    "Row 23: Missing required field"
  ]
}
```

**Sample CSV Template:**
```csv
permit_record_number,date,permit_type,project_description,job_address,job_cost,permit_status,email,phone_number,country,city,state,work_type,credit_cost,category
P-2025-001,2025-11-15,Building Permit,New construction,123 Main St,500000,Approved,contact@example.com,(555) 123-4567,USA,Miami,Florida,Residential,1,Construction
```

#### POST `/jobs/filter`
Filter and search jobs based on location and work type.

**Query Parameters:**
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 25, max: 100)

**Request:**
```json
{
  "cities": ["Miami", "Orlando"],
  "countries": ["USA"],
  "work_types": ["Residential", "Commercial"],
  "states": ["Florida", "Georgia"]
}
```

**Response:**
```json
{
  "jobs": [
    {
      "id": 1,
      "permit_record_number": "P-2025-001",
      "date": "2025-11-15",
      "permit_type": "Building Permit",
      "project_description": "New construction",
      "job_address": "123 Main St, Miami, FL",
      "job_cost": "$500,000",
      "permit_status": "Approved",
      "country": "USA",
      "city": "Miami",
      "state": "Florida",
      "work_type": "Residential",
      "created_at": "2025-11-20T10:00:00"
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 25,
  "total_pages": 6
}
```

#### POST `/jobs/unlock/{job_id}`
Unlock a job by spending 1 credit.

**Response:**
```json
{
  "id": 1,
  "permit_record_number": "P-2025-001",
  "date": "2025-11-15",
  "permit_type": "Building Permit",
  "project_description": "New construction",
  "job_address": "123 Main St, Miami, FL",
  "job_cost": "$500,000",
  "permit_status": "Approved",
  "email": "contact@example.com",
  "phone_number": "(555) 123-4567",
  "country": "USA",
  "city": "Miami",
  "state": "Florida",
  "work_type": "Residential",
  "created_at": "2025-11-20T10:00:00"
}
```

#### GET `/jobs/my-unlocked-leads`
Get all unlocked leads for the current user.

**Query Parameters:**
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 25, max: 100)

**Response:**
```json
{
  "unlocked_leads": [
    {
      "unlocked_lead_id": 1,
      "job_id": 1,
      "permit_record_number": "P-2025-001",
      "email": "contact@example.com",
      "phone_number": "(555) 123-4567",
      "credits_spent": 1,
      "unlocked_at": "2025-11-19T15:30:00"
    }
  ],
  "total": 15,
  "page": 1,
  "page_size": 25,
  "total_pages": 1
}
```

#### GET `/jobs/export-unlocked-leads`
Export all unlocked leads to CSV file.

**Response:** CSV file download with all unlocked lead details.

### Dashboard Endpoint

#### GET `/dashboard`
Get dashboard information after login (requires completed profile).

**Query Parameters:**
- `page`: Page number for recent leads (default: 1)
- `page_size`: Items per page (default: 25, max: 100)

**Response:**
```json
{
  "user_email": "user@example.com",
  "role": "Contractor",
  "is_profile_complete": true,
  "credit_balance": 285,
  "credits_added_this_week": 300,
  "active_subscription": "Pro",
  "subscription_renew_date": "2025-12-20T10:00:00",
  "total_jobs_unlocked": 15,
  "total_available_jobs": 150,
  "recent_leads": [
    {
      "id": 1,
      "permit_record_number": "P-2025-001",
      "date": "2025-11-15",
      "permit_type": "Building Permit",
      "project_description": "New construction",
      "job_address": "123 Main St, Miami, FL",
      "job_cost": "$500,000",
      "permit_status": "Approved",
      "country": "USA",
      "city": "Miami",
      "state": "Florida",
      "work_type": "Residential",
      "created_at": "2025-11-20T10:00:00"
    }
  ],
  "current_page": 1,
  "total_pages": 6
}
```

### Login Endpoint (Updated)

#### POST `/api/login`
Login endpoint now returns additional information.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "redirect_to_dashboard": true,
  "is_profile_complete": true,
  "role": "Contractor"
}
```

## Setup Instructions

### 1. Run Database Migrations
The new tables will be automatically created when you start the server.

### 2. Seed Subscription Plans
Run the seed script to create the three subscription tiers:

```bash
python seed_subscriptions.py
```

This creates:
- Starter: $89.99/month – 100 tokens
- Pro: $199.99/month – 300 tokens
- Elite: $499.99/month – 1000 tokens

### 3. Authentication
All endpoints (except `/subscription/plans`) require authentication:

```
Authorization: Bearer <access_token>
```

## User Flow

1. **Registration & Profile Setup**
   - User registers and verifies email
   - User selects role (Contractor/Supplier)
   - User completes 4-step profile registration

2. **Login & Dashboard**
   - User logs in
   - If profile is complete (`is_completed: true`), redirect to dashboard
   - Dashboard shows available jobs based on user's location/work type preferences

3. **Browse Jobs**
   - User sees jobs filtered by their profile (state, work type, etc.)
   - User can apply additional filters (cities, countries, work types)
   - Pagination: 25 leads per page

4. **Subscribe to Plan**
   - User subscribes to a plan (Starter/Pro/Elite)
   - Credits are added to their account

5. **Unlock Leads**
   - User spends 1 credit to unlock a job
   - Email and phone number are revealed
   - Lead is added to "My Unlocked Leads"

6. **View Unlocked Leads**
   - User can view all unlocked leads
   - Export all unlocked leads to CSV

7. **Monitor Wallet**
   - View current credit balance
   - See subscription renewal date
   - Track spending history

## Filtering Logic

### For Contractors:
- Jobs filtered by `service_state` (from Step 4 of contractor registration)
- Jobs filtered by `work_type` (from Step 3 of contractor registration)

### For Suppliers:
- Jobs filtered by `service_states` (from Step 2 of supplier registration)
- Multiple states supported

### Additional Filters:
Users can further filter by:
- Cities
- Countries
- Work types
- States

## Notes

- Each job unlock costs 1 credit
- Users cannot unlock the same job twice
- Dashboard only accessible with completed profile
- Jobs API automatically filters based on user profile
- CSV export includes all unlocked lead details
