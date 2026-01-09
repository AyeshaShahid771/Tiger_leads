# Jobs Endpoints API Documentation

This document provides detailed information about the main jobs endpoints, including their parameters, response formats, and usage examples.

---

## Table of Contents

1. [GET /jobs/all](#get-jobsall)
2. [GET /jobs/feed](#get-jobsfeed)
3. [GET /jobs/search](#get-jobssearch)
4. [POST /jobs/my-feed-not-interested/{job_id}](#post-jobsmy-feed-not-interestedjob_id)

---

## GET /jobs/all

Retrieves all available jobs matching the user's profile with pagination. No manual filters required - automatically matches based on user type and location from the user's contractor/supplier profile.

### Description

- **For Contractors**: Matches jobs based on user_type array and filters by states and country_city from contractor profile
- **For Suppliers**: Matches jobs based on user_type array and filters by service_states and country_city from supplier profile
- Uses the same matching logic as the dashboard
- Excludes jobs marked as not interested, unlocked, and saved jobs
- Returns only posted jobs

### Authentication

Requires authentication token in the header.

### Query Parameters

| Parameter   | Type    | Required | Default | Description                          |
|-------------|---------|----------|---------|--------------------------------------|
| `page`      | integer | No       | 1       | Page number (minimum: 1)             |
| `page_size` | integer | No       | 20      | Number of jobs per page (1-100)      |

### Response Format

```json
{
  "jobs": [
    {
      "id": 123,
      "trs_score": 85,
      "permit_type": "Electrical Project",
      "country_city": "Los Angeles County",
      "state": "CA",
      "project_description": "Residential electrical upgrade...",
      "review_posted_at": "2026-01-09T10:30:00",
      "saved": false
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 20,
  "total_pages": 8
}
```

### Response Fields

| Field              | Type    | Description                                    |
|-------------------|---------|------------------------------------------------|
| `jobs`            | array   | Array of job objects                           |
| `jobs[].id`       | integer | Unique job identifier                          |
| `jobs[].trs_score`| integer | TRS quality score (0-100)                      |
| `jobs[].permit_type` | string | Type of permit/project                      |
| `jobs[].country_city` | string | County or city location                    |
| `jobs[].state`    | string  | State abbreviation                             |
| `jobs[].project_description` | string | Description of the project       |
| `jobs[].review_posted_at` | datetime | When the job was posted         |
| `jobs[].saved`    | boolean | Whether job is saved by user                   |
| `total`           | integer | Total number of matching jobs                  |
| `page`            | integer | Current page number                            |
| `page_size`       | integer | Number of jobs per page                        |
| `total_pages`     | integer | Total number of pages                          |

### Example Request

```bash
GET /jobs/all?page=1&page_size=20
Authorization: Bearer <token>
```

### Example Response

```json
{
  "jobs": [
    {
      "id": 1001,
      "trs_score": 92,
      "permit_type": "Plumbing Project",
      "country_city": "Orange County",
      "state": "CA",
      "project_description": "Commercial plumbing installation for new office building",
      "review_posted_at": "2026-01-09T14:25:00",
      "saved": false
    },
    {
      "id": 1002,
      "trs_score": 78,
      "permit_type": "HVAC Project",
      "country_city": "San Diego County",
      "state": "CA",
      "project_description": "Replace HVAC system in 3000 sq ft residential property",
      "review_posted_at": "2026-01-09T12:15:00",
      "saved": false
    }
  ],
  "total": 45,
  "page": 1,
  "page_size": 20,
  "total_pages": 3
}
```

### Error Responses

| Status Code | Description                                      |
|-------------|--------------------------------------------------|
| 400         | Profile incomplete - user must complete profile  |
| 403         | User must be a Contractor or Supplier            |
| 401         | Authentication required                          |

---

## GET /jobs/feed

Returns a filtered list of jobs based on custom filters for states, countries, or user categories. Provides more granular control than `/jobs/all`.

### Description

- Allows filtering by user type, states, and countries/cities
- At least one filter parameter is required
- Excludes not interested, unlocked, and saved jobs
- Returns only posted jobs
- Ordered by newest first (review_posted_at)

### Authentication

Requires authentication token in the header.

### Query Parameters

| Parameter   | Type   | Required | Default | Description                                      |
|-------------|--------|----------|---------|--------------------------------------------------|
| `user_type` | string | No*      | -       | Comma-separated list of user types               |
| `states`    | string | No*      | -       | Comma-separated list of states (e.g., "CA,TX")   |
| `countries` | string | No*      | -       | Comma-separated list of countries/cities         |
| `page`      | integer| No       | 1       | Page number (minimum: 1)                         |
| `page_size` | integer| No       | 20      | Number of jobs per page (1-100)                  |

**Note**: At least one of `user_type`, `states`, or `countries` must be provided.

### Response Format

```json
{
  "jobs": [
    {
      "id": 456,
      "trs_score": 88,
      "permit_type": "Electrical Project",
      "country_city": "Cook County",
      "state": "IL",
      "project_description": "Industrial electrical panel upgrade...",
      "saved": false
    }
  ],
  "total": 75,
  "page": 1,
  "page_size": 20,
  "total_pages": 4
}
```

### Response Fields

| Field              | Type    | Description                                    |
|-------------------|---------|------------------------------------------------|
| `jobs`            | array   | Array of job objects                           |
| `jobs[].id`       | integer | Unique job identifier                          |
| `jobs[].trs_score`| integer | TRS quality score (0-100)                      |
| `jobs[].permit_type` | string | Type of permit/project                      |
| `jobs[].country_city` | string | County or city location                    |
| `jobs[].state`    | string  | State abbreviation                             |
| `jobs[].project_description` | string | Description of the project       |
| `jobs[].saved`    | boolean | Whether job is saved by user                   |
| `total`           | integer | Total number of matching jobs                  |
| `page`            | integer | Current page number                            |
| `page_size`       | integer | Number of jobs per page                        |
| `total_pages`     | integer | Total number of pages                          |

### Example Request

```bash
GET /jobs/feed?user_type=plumber,electrician&states=CA,TX&page=1&page_size=10
Authorization: Bearer <token>
```

### Example Response

```json
{
  "jobs": [
    {
      "id": 2001,
      "trs_score": 95,
      "permit_type": "Electrical Project",
      "country_city": "Harris County",
      "state": "TX",
      "project_description": "Commercial electrical wiring for new warehouse facility",
      "saved": false
    },
    {
      "id": 2002,
      "trs_score": 87,
      "permit_type": "Plumbing Project",
      "country_city": "Los Angeles County",
      "state": "CA",
      "project_description": "Residential re-piping project, 2-story home",
      "saved": false
    }
  ],
  "total": 28,
  "page": 1,
  "page_size": 10,
  "total_pages": 3
}
```

### Error Responses

| Status Code | Description                                                        |
|-------------|--------------------------------------------------------------------|
| 400         | At least one filter (user_type, states, or countries) is required |
| 403         | User must be a Contractor or Supplier                              |
| 401         | Authentication required                                            |

---

## GET /jobs/search

Searches for jobs across all fields using a keyword. Performs a comprehensive search across multiple job attributes.

### Description

- Searches across: permit type, project description, job address, permit status, email, phone number, country/city, state, work type, and category
- Case-insensitive keyword matching
- Excludes jobs marked as not interested, unlocked, and saved jobs
- Returns both posted jobs and jobs without review status
- Ordered by newest first (review_posted_at)

### Authentication

Requires authentication token in the header.

### Query Parameters

| Parameter   | Type    | Required | Default | Description                                  |
|-------------|---------|----------|---------|----------------------------------------------|
| `keyword`   | string  | Yes      | -       | Search keyword (minimum 1 character)         |
| `page`      | integer | No       | 1       | Page number (minimum: 1)                     |
| `page_size` | integer | No       | 20      | Number of jobs per page (1-100)              |

### Response Format

```json
{
  "jobs": [
    {
      "id": 789,
      "trs_score": 90,
      "permit_type": "Roofing Project",
      "country_city": "Miami-Dade County",
      "state": "FL",
      "project_description": "Commercial roof replacement...",
      "review_posted_at": "2026-01-08T16:45:00",
      "saved": false
    }
  ],
  "total": 12,
  "page": 1,
  "page_size": 20,
  "total_pages": 1,
  "keyword": "roof"
}
```

### Response Fields

| Field              | Type    | Description                                    |
|-------------------|---------|------------------------------------------------|
| `jobs`            | array   | Array of job objects                           |
| `jobs[].id`       | integer | Unique job identifier                          |
| `jobs[].trs_score`| integer | TRS quality score (0-100)                      |
| `jobs[].permit_type` | string | Type of permit/project                      |
| `jobs[].country_city` | string | County or city location                    |
| `jobs[].state`    | string  | State abbreviation                             |
| `jobs[].project_description` | string | Description of the project       |
| `jobs[].review_posted_at` | datetime | When the job was posted         |
| `jobs[].saved`    | boolean | Whether job is saved by user                   |
| `total`           | integer | Total number of matching jobs                  |
| `page`            | integer | Current page number                            |
| `page_size`       | integer | Number of jobs per page                        |
| `total_pages`     | integer | Total number of pages                          |
| `keyword`         | string  | The search keyword used                        |

### Fields Searched

The keyword search matches against the following fields:
- Permit type (permit_type_norm)
- Project description
- Job address
- Permit status
- Contractor email
- Contractor phone
- County/city (source_county)
- State
- Audience type slugs (categories)

### Example Request

```bash
GET /jobs/search?keyword=electrical&page=1&page_size=15
Authorization: Bearer <token>
```

### Example Response

```json
{
  "jobs": [
    {
      "id": 3001,
      "trs_score": 91,
      "permit_type": "Electrical Project",
      "country_city": "Maricopa County",
      "state": "AZ",
      "project_description": "Electrical panel upgrade for commercial building",
      "review_posted_at": "2026-01-09T09:20:00",
      "saved": false
    },
    {
      "id": 3002,
      "trs_score": 84,
      "permit_type": "Electrical Project",
      "country_city": "King County",
      "state": "WA",
      "project_description": "Install electrical wiring for new construction residential home",
      "review_posted_at": "2026-01-08T15:30:00",
      "saved": false
    }
  ],
  "total": 23,
  "page": 1,
  "page_size": 15,
  "total_pages": 2,
  "keyword": "electrical"
}
```

### Error Responses

| Status Code | Description                     |
|-------------|---------------------------------|
| 400         | Keyword parameter is required   |
| 401         | Authentication required         |

---

## POST /jobs/my-feed-not-interested/{job_id}

Permanently hides a specific job from all feeds by marking it as "not interested."

### Description

- Adds the job to the user's not-interested list
- Job will no longer appear in any feeds (/jobs/feed, /jobs/all, /jobs/my-job-feed, etc.)
- If the job was previously saved, it will be removed from saved jobs
- Can only be used on posted jobs
- Action is permanent (cannot be undone via this endpoint)

### Authentication

Requires authentication token in the header.

### Path Parameters

| Parameter | Type    | Required | Description              |
|-----------|---------|----------|--------------------------|
| `job_id`  | integer | Yes      | The ID of the job to hide|

### Request Body

No request body required.

### Response Format

```json
{
  "message": "Job marked as not interested successfully",
  "job_id": 123
}
```

### Response Fields

| Field     | Type    | Description                               |
|-----------|---------|-------------------------------------------|
| `message` | string  | Success or informational message          |
| `job_id`  | integer | The ID of the job that was marked         |

### Example Request

```bash
POST /jobs/my-feed-not-interested/1234
Authorization: Bearer <token>
```

### Example Response (Success)

```json
{
  "message": "Job marked as not interested successfully",
  "job_id": 1234
}
```

### Example Response (Already Marked)

```json
{
  "message": "Job already marked as not interested",
  "job_id": 1234
}
```

### Behavior Notes

1. **If job was saved**: The job is automatically removed from the user's saved jobs list before being marked as not interested
2. **If already marked**: Returns a success message indicating the job was already marked
3. **Permanent action**: Once marked as not interested, the job will not appear in feeds unless manually removed from the not-interested list (requires database operation)

### Error Responses

| Status Code | Description                                          |
|-------------|------------------------------------------------------|
| 404         | Job not found or job is not in posted status         |
| 401         | Authentication required                              |

---

## Common Response Patterns

### Pagination

All list endpoints support pagination with the following common parameters:
- `page`: Current page number (starts at 1)
- `page_size`: Number of items per page (typically 1-100)

Pagination information in responses:
- `total`: Total number of items matching the query
- `page`: Current page number
- `page_size`: Number of items per page
- `total_pages`: Total number of pages

### Job Object Fields

Common fields across job objects:

| Field               | Type     | Description                          |
|---------------------|----------|--------------------------------------|
| `id`                | integer  | Unique job identifier                |
| `trs_score`         | integer  | TRS quality score (0-100)            |
| `permit_type`       | string   | Type of permit/project               |
| `country_city`      | string   | County or city (from source_county)  |
| `state`             | string   | State abbreviation                   |
| `project_description` | string | Project description                |
| `review_posted_at`  | datetime | When job was approved and posted     |
| `saved`             | boolean  | Whether user has saved this job      |

### Authentication

All endpoints require a valid JWT token in the Authorization header:

```
Authorization: Bearer <your-token-here>
```

### Common Filters

These endpoints automatically exclude:
- Jobs marked as "not interested" by the user
- Jobs already unlocked (purchased) by the user
- Jobs saved by the user (in most cases)

---

## Notes

1. **TRS Score**: Higher scores (closer to 100) indicate higher quality leads based on completeness of information
2. **Review Status**: Jobs are typically in "posted" status to appear in feeds
3. **Role Requirements**: Most endpoints require user to be either a Contractor or Supplier
4. **Profile Completion**: `/jobs/all` requires a completed profile to match jobs effectively

---

## Related Endpoints

- `GET /jobs/all-my-jobs` - View all unlocked (purchased) jobs
- `GET /jobs/my-job-feed` - Filtered feed of unlocked jobs
- `GET /jobs/saved-jobs` - View saved jobs
- `POST /jobs/unlock/{job_id}` - Purchase/unlock a job to view full details
- `POST /jobs/save/{job_id}` - Save a job for later
