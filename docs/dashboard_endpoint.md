# Dashboard API Documentation

## GET /dashboard — Get User Dashboard Data

### Overview

Returns comprehensive dashboard information for authenticated contractors and suppliers, including credit balance, subscription details, and top 20 matched jobs based on their profile.

### Endpoint

```
GET /dashboard
```

### Authentication

**Required**: Bearer Token (JWT)

**Headers:**

```
Authorization: Bearer <jwt_token>
```

### User Roles

- **Contractor**: Returns jobs matched to trade categories and service locations
- **Supplier**: Returns jobs matched to product categories and service states

### Request

No request body or query parameters required.

### Response Model

**Pydantic Schema**: `DashboardResponse`

| Field                      | Type                       | Description                                                                   |
| -------------------------- | -------------------------- | ----------------------------------------------------------------------------- |
| `credit_balance`           | `int`                      | Current available credits for unlocking jobs                                  |
| `credits_added_this_week`  | `int`                      | Credits added in the last 7 days                                              |
| `plan_name`                | `string`                   | Current subscription plan name (e.g., "Starter", "Pro", "Elite", "Free Plan") |
| `renewal_date`             | `string` (nullable)        | Next renewal date in format "February 2025"                                   |
| `profile_completion_month` | `string` (nullable)        | Month when profile was completed (e.g., "December 2024")                      |
| `total_jobs_unlocked`      | `int`                      | Total number of jobs unlocked by this user                                    |
| `top_matched_jobs`         | `array[MatchedJobSummary]` | Top 20 matched jobs ordered by TRS score                                      |

#### MatchedJobSummary Object

| Field          | Type                | Description                   |
| -------------- | ------------------- | ----------------------------- |
| `id`           | `int`               | Unique job ID                 |
| `trs_score`    | `int` (nullable)    | Total Relevance Score (0-100) |
| `permit_type`  | `string` (nullable) | Type of permit/job            |
| `country_city` | `string` (nullable) | County or city location       |
| `state`        | `string` (nullable) | State location                |

### Success Response (200 OK)

#### Example Response - Contractor

```json
{
  "credit_balance": 150,
  "credits_added_this_week": 300,
  "plan_name": "Pro",
  "renewal_date": "January 2025",
  "profile_completion_month": "December 2024",
  "total_jobs_unlocked": 25,
  "top_matched_jobs": [
    {
      "id": 325,
      "trs_score": 95,
      "permit_type": "Residential Building Trade New Construction and Additions",
      "country_city": "Hillsborough County",
      "state": "Florida"
    },
    {
      "id": 324,
      "trs_score": 88,
      "permit_type": "Commercial Electrical Work",
      "country_city": "Miami-Dade County",
      "state": "Florida"
    }
  ]
}
```

#### Example Response - Free Plan User

```json
{
  "credit_balance": 0,
  "credits_added_this_week": 0,
  "plan_name": "Free Plan",
  "renewal_date": null,
  "profile_completion_month": "December 2024",
  "total_jobs_unlocked": 0,
  "top_matched_jobs": [
    {
      "id": 456,
      "trs_score": 67,
      "permit_type": "Residential Plumbing Trade Permit",
      "country_city": "Hillsborough County",
      "state": "Florida"
    }
  ]
}
```

### Error Responses

#### 401 Unauthorized

```json
{
  "detail": "Not authenticated"
}
```

**Cause**: Missing or invalid JWT token

#### 403 Forbidden - Invalid Role

```json
{
  "detail": "User must be a Contractor or Supplier to access dashboard"
}
```

**Cause**: User role is neither "Contractor" nor "Supplier"

#### 403 Forbidden - Incomplete Profile

```json
{
  "detail": "Please complete your profile to access the dashboard"
}
```

**Cause**: User profile is not completed (`is_completed = false`)

### Business Logic

#### 1. Plan Name Logic

- **Free Plan**: Displayed when `credit_balance = 0` AND `total_spent = 0`
- **Paid Plan**: Shows subscription name (Starter/Pro/Elite) when user has an active subscription

#### 2. Credits Added This Week

- Calculates credits added if subscription started within last 7 days
- Returns `0` if subscription is older than 7 days or no subscription

#### 3. Matched Jobs Algorithm

**For Contractors:**

1. Fetch user's `trade_categories` from profile
2. Get keywords associated with the trade category
3. Search jobs where keywords match `permit_type` OR `project_description` (case-insensitive)
4. Filter by user's service `state` (ARRAY field)
5. Filter by user's service `country_city` (ARRAY field)
6. Exclude jobs already unlocked by user
7. Exclude jobs marked as "not interested" by user
8. Order by `trs_score` DESC, then `created_at` DESC
9. Return top 20 results

**For Suppliers:**

1. Fetch user's `product_categories` from profile
2. Get keywords associated with the product category
3. Search jobs where keywords match `permit_type` OR `project_description` (case-insensitive)
4. Filter by user's `service_states` (ARRAY field)
5. Filter by user's service `country_city` (ARRAY field)
6. Exclude jobs already unlocked by user
7. Exclude jobs marked as "not interested" by user
8. Order by `trs_score` DESC, then `created_at` DESC
9. Return top 20 results

#### 4. Job Exclusion Logic

Jobs are **excluded** from results if:

- User has already unlocked the job (exists in `unlocked_leads` table)
- User marked job as "not interested" (exists in `not_interested_jobs` table)

#### 5. TRS Score (Total Relevance Score)

Jobs are ranked by TRS score (0-100) calculated from:

- **25%** - Project value/cost
- **25%** - Permit stage/status
- **20%** - Contact information availability
- **20%** - Description quality
- **10%** - Address completeness

### Notes

1. **Profile Required**: User must have a completed contractor or supplier profile
2. **Automatic Matching**: Jobs are automatically matched based on profile categories and locations
3. **Real-time Exclusions**: Unlocked and not-interested jobs are dynamically excluded
4. **Top 20 Limit**: Only top 20 jobs are returned (use `/dashboard/matched-jobs` for pagination)
5. **Logging**: Server logs all job IDs sent to user for debugging

### Related Endpoints

- `GET /dashboard/matched-jobs` - Paginated matched jobs with exclusion support
- `POST /dashboard/unlock-job` - Unlock a job by spending credits
- `POST /dashboard/mark-not-interested` - Mark job as not interested

### Implementation Details

**Database Tables Used:**

- `users` - User authentication
- `contractors` / `suppliers` - Profile data
- `subscribers` - Credit balance and subscription info
- `subscriptions` - Plan details
- `jobs` - Job listings
- `unlocked_leads` - Unlocked job tracking
- `not_interested_jobs` - Not interested job tracking

**Performance Considerations:**

- Keyword matching uses database ILIKE (case-insensitive LIKE)
- Multiple OR conditions for keyword searches
- Array field filtering for locations
- Indexed queries on `user_id` and `job_id`

### Example Usage

#### cURL

```bash
curl -X GET "https://api.tigerleads.ai/dashboard" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### Python

```python
import requests

headers = {
    "Authorization": f"Bearer {jwt_token}"
}

response = requests.get(
    "https://api.tigerleads.ai/dashboard",
    headers=headers
)

data = response.json()
print(f"Credit Balance: {data['credit_balance']}")
print(f"Plan: {data['plan_name']}")
print(f"Top Jobs: {len(data['top_matched_jobs'])}")
```

#### JavaScript/Axios

```javascript
const response = await axios.get("https://api.tigerleads.ai/dashboard", {
  headers: {
    Authorization: `Bearer ${jwtToken}`,
  },
});

console.log("Credit Balance:", response.data.credit_balance);
console.log("Top Jobs:", response.data.top_matched_jobs);
```

---

**Last Updated**: December 5, 2025  
**API Version**: 1.0  
**Status**: Production Ready ✅
