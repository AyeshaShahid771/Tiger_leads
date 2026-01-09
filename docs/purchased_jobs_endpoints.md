# Purchased Jobs Endpoints API

## GET /jobs/all-my-jobs

Get all unlocked jobs for the current user with pagination.

**Response:**
```json
{
  "jobs": [
    {
      "id": 123,
      "trs_score": 85,
      "permit_type": "Building Permit",
      "country_city": "Orange County",
      "state": "CA",
      "project_description": "Kitchen remodel",
      "job_cost": 50000,
      "job_address": "123 Main St",
      "review_posted_at": "2024-01-15T10:30:00",
      "saved": true
    }
  ],
  "total": 100,
  "page": 1,
  "page_size": 20,
  "total_pages": 5
}
```

---

## GET /jobs/all-my-jobs-desktop

Get all unlocked jobs for desktop view with detailed information including contact info.

**Response:**
```json
{
  "jobs": [
    {
      "id": 123,
      "permit_type": "Building Permit",
      "job_cost": 50000,
      "job_address": "123 Main St",
      "trs_score": 85,
      "email": "contractor@example.com",
      "phone_number": "555-1234",
      "country_city": "Orange County",
      "state": "CA",
      "project_description": "Kitchen remodel",
      "review_posted_at": "2024-01-15T10:30:00",
      "saved": true
    }
  ],
  "total": 100,
  "page": 1,
  "page_size": 20,
  "total_pages": 5
}
```

---

## GET /jobs/all-my-jobs-desktop-search

Search unlocked jobs for desktop view with keyword filtering.

**Response:**
```json
{
  "jobs": [
    {
      "id": 123,
      "permit_type": "Building Permit",
      "job_cost": 50000,
      "job_address": "123 Main St",
      "trs_score": 85,
      "email": "contractor@example.com",
      "phone_number": "555-1234",
      "country_city": "Orange County",
      "state": "CA",
      "project_description": "Kitchen remodel",
      "review_posted_at": "2024-01-15T10:30:00",
      "saved": true
    }
  ],
  "total": 25,
  "page": 1,
  "page_size": 20,
  "total_pages": 2
}
```

---

## GET /jobs/my-job-feed

Get unlocked jobs feed with custom filters (user_type, states, countries).

**Response:**
```json
{
  "jobs": [
    {
      "id": 123,
      "trs_score": 85,
      "permit_type": "Building Permit",
      "country_city": "Orange County",
      "state": "CA",
      "project_description": "Kitchen remodel",
      "job_cost": 50000,
      "job_address": "123 Main St",
      "review_posted_at": "2024-01-15T10:30:00"
    }
  ],
  "total": 50,
  "page": 1,
  "page_size": 20,
  "total_pages": 3
}
```

---

## GET /jobs/view-details/{job_id}

View complete details of an unlocked job including user's notes.

**Response:**
```json
{
  "id": 123,
  "permit_number": "2024-001234",
  "permit_type": "Building Permit",
  "permit_type_norm": "Building",
  "permit_status": "Issued",
  "job_cost": 50000,
  "job_address": "123 Main St",
  "country_city": "Orange County",
  "state": "CA",
  "project_description": "Kitchen remodel",
  "email": "contractor@example.com",
  "phone_number": "555-1234",
  "trs_score": 85,
  "review_posted_at": "2024-01-15T10:30:00",
  "notes": "Follow up next week",
  "unlocked_at": "2024-01-10T14:20:00"
}
```

---

## PUT /jobs/update-notes/{job_id}

Update notes for an unlocked job.

**Response:**
```json
{
  "message": "Notes updated successfully",
  "job_id": 123,
  "notes": "Follow up with client next week"
}
```

---

## POST /jobs/my-feed-not-interested/{job_id}

Mark a job from my feed as not interested.

**Response:**
```json
{
  "message": "Job marked as not interested",
  "job_id": 123
}
```

---

## GET /jobs/all-my-saved-jobs

Get all saved jobs for the current user without any filters.

**Response:**
```json
{
  "jobs": [
    {
      "id": 123,
      "trs_score": 85,
      "permit_type": "Building Permit",
      "country_city": "Orange County",
      "state": "CA",
      "project_description": "Kitchen remodel",
      "saved": true
    }
  ],
  "total": 50,
  "page": 1,
  "page_size": 20,
  "total_pages": 3
}
```

---

## GET /jobs/my-saved-job-feed

Get saved jobs feed with custom filters (user_type, states, countries).

**Response:**
```json
{
  "jobs": [
    {
      "id": 123,
      "trs_score": 85,
      "permit_type": "Building Permit",
      "country_city": "Orange County",
      "state": "CA",
      "project_description": "Kitchen remodel",
      "saved": true
    }
  ],
  "total": 25,
  "page": 1,
  "page_size": 20,
  "total_pages": 2
}
```
