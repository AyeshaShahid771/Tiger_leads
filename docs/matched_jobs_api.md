# Matched Jobs API Documentation

## Endpoint: `GET /api/jobs/matched-jobs`

Fetch jobs that match contractor's trade categories from their database profile. The endpoint automatically reads the `trade_specialities` array from the contractor's profile and searches for jobs matching **ALL** their selected trade categories.

### Authentication
Requires JWT Bearer token in Authorization header. **User must be a Contractor with a completed profile.**

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `page` | integer | No | Page number (default: 1, min: 1) |
| `page_size` | integer | No | Items per page (default: 50, min: 1, max: 500) |
| `min_trs_score` | integer | No | Minimum TRS score (0-100) |
| `max_trs_score` | integer | No | Maximum TRS score (0-100) |
| `state` | string | No | Filter by state (e.g., "Georgia", "Florida") |
| `country_city` | string | No | Filter by city or county (e.g., "Atlanta", "Hillsborough County") |

### Trade Categories

The following 14 trade categories are supported:

1. **General contracting & building**
2. **Interior construction & finishes**
3. **Electrical, low-voltage & solar**
4. **Mechanical, HVAC & refrigeration**
5. **Plumbing, gas & medical gas**
6. **Fire protection systems**
7. **Roofing, windows & exterior envelope**
8. **Sitework, utilities & civil**
9. **Landscaping, pools & outdoor features**
10. **Environmental, abatement & hazardous materials**
11. **Accessibility, elevators & conveyance**
12. **Temporary works & construction support**
13. **Zoning, entitlements & environmental review**
14. **Occupancy, final inspections & assembly**

### How Matching Works

The endpoint searches for jobs where the `permit_type` or `project_description` contains any of the keywords associated with the selected trade categories.

For example, if a contractor selects **"Electrical, low-voltage & solar"**, the system will match jobs containing keywords like:
- electrical
- low voltage
- solar
- pv (photovoltaic)
- ev (electric vehicle)
- lighting
- data
- security
- And many more...

Multiple trade categories can be selected, and jobs matching **ANY** of the selected categories will be returned.

### Response Format

```json
{
  "jobs": [
    {
      "id": 123,
      "permit_record_number": "2024-001234",
      "date": "2024-12-01T00:00:00",
      "permit_type": "Electrical",
      "project_description": "Install solar panels and EV charger",
      "job_address": "123 Main St, Atlanta, GA 30301",
      "job_cost": "50000",
      "permit_status": "Issued",
      "email": null,
      "phone_number": null,
      "country_city": "Atlanta",
      "state": "Georgia",
      "work_type": "Electrical",
      "credit_cost": 1,
      "category": "Residential",
      "trs_score": 75,
      "is_unlocked": false,
      "created_at": "2024-12-01T10:30:00",
      "updated_at": "2024-12-01T10:30:00"
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 50,
  "total_pages": 3
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Unique job ID |
| `permit_record_number` | string | Permit/record number |
| `date` | datetime | Job date |
| `permit_type` | string | Type of permit (Project Type) |
| `project_description` | string | Detailed project description |
| `job_address` | string | Job site address |
| `job_cost` | string | Project value/cost |
| `permit_status` | string | Current permit status |
| `email` | string | Contractor email (null if not unlocked) |
| `phone_number` | string | Contractor phone (null if not unlocked) |
| `country_city` | string | City or county name |
| `state` | string | Full state name (e.g., "Georgia") |
| `work_type` | string | Type of work |
| `credit_cost` | integer | Credits required to unlock |
| `category` | string | Job category |
| `trs_score` | integer | Total Relevance Score (0-100) |
| `is_unlocked` | boolean | Whether current user has unlocked this job |
| `created_at` | datetime | When job was created |
| `updated_at` | datetime | When job was last updated |

### Example Requests

#### 1. Basic Request - Single Trade Category

```bash
GET /api/jobs/matched-jobs?trade_categories=Electrical%2C%20low-voltage%20%26%20solar&page=1&page_size=50
Authorization: Bearer <your_jwt_token>
```

#### 2. Multiple Trade Categories

```bash
GET /api/jobs/matched-jobs?trade_categories=Electrical%2C%20low-voltage%20%26%20solar&trade_categories=Mechanical%2C%20HVAC%20%26%20refrigeration&page=1&page_size=50
Authorization: Bearer <your_jwt_token>
```

#### 3. With TRS Score Filter

```bash
GET /api/jobs/matched-jobs?trade_categories=General%20contracting%20%26%20building&min_trs_score=70&max_trs_score=100&page=1&page_size=50
Authorization: Bearer <your_jwt_token>
```

#### 4. With Location Filters

```bash
GET /api/jobs/matched-jobs?trade_categories=Plumbing%2C%20gas%20%26%20medical%20gas&state=Georgia&country_city=Atlanta&page=1&page_size=50
Authorization: Bearer <your_jwt_token>
```

#### 5. Python Example

```python
import requests

url = "http://your-api-domain.com/api/jobs/matched-jobs"

headers = {
    "Authorization": "Bearer your_jwt_token_here"
}

params = {
    "trade_categories": [
        "Electrical, low-voltage & solar",
        "General contracting & building"
    ],
    "page": 1,
    "page_size": 50,
    "min_trs_score": 60,
    "state": "Georgia"
}

response = requests.get(url, headers=headers, params=params)
data = response.json()

print(f"Total jobs found: {data['total']}")
print(f"Page {data['page']} of {data['total_pages']}")
print(f"Jobs on this page: {len(data['jobs'])}")

for job in data['jobs']:
    print(f"\nJob ID: {job['id']}")
    print(f"Type: {job['permit_type']}")
    print(f"Location: {job['country_city']}, {job['state']}")
    print(f"TRS Score: {job['trs_score']}")
    print(f"Cost: ${job['job_cost']}")
```

#### 6. JavaScript/Fetch Example

```javascript
const url = new URL('http://your-api-domain.com/api/jobs/matched-jobs');

const params = {
    trade_categories: [
        'Electrical, low-voltage & solar',
        'Mechanical, HVAC & refrigeration'
    ],
    page: 1,
    page_size: 50,
    min_trs_score: 70
};

// Add multiple trade_categories as separate params
url.searchParams.append('trade_categories', params.trade_categories[0]);
url.searchParams.append('trade_categories', params.trade_categories[1]);
url.searchParams.append('page', params.page);
url.searchParams.append('page_size', params.page_size);
url.searchParams.append('min_trs_score', params.min_trs_score);

fetch(url, {
    method: 'GET',
    headers: {
        'Authorization': 'Bearer your_jwt_token_here',
        'Content-Type': 'application/json'
    }
})
.then(response => response.json())
.then(data => {
    console.log(`Total jobs: ${data.total}`);
    console.log(`Page ${data.page} of ${data.total_pages}`);
    
    data.jobs.forEach(job => {
        console.log(`\nJob: ${job.permit_type}`);
        console.log(`Location: ${job.country_city}, ${job.state}`);
        console.log(`TRS: ${job.trs_score}`);
    });
})
.catch(error => console.error('Error:', error));
```

### Error Responses

#### 400 Bad Request - Invalid Trade Category

```json
{
  "detail": "Invalid trade category: Invalid Category. Valid categories: General contracting & building, Interior construction & finishes, ..."
}
```

#### 401 Unauthorized - Missing/Invalid Token

```json
{
  "detail": "Not authenticated"
}
```

#### 422 Validation Error - Invalid Parameters

```json
{
  "detail": [
    {
      "loc": ["query", "min_trs_score"],
      "msg": "ensure this value is greater than or equal to 0",
      "type": "value_error.number.not_ge"
    }
  ]
}
```

### Notes

1. **Contact Information Protection**: `email` and `phone_number` fields are only visible if the current user has unlocked that specific job. Otherwise, they return `null`.

2. **Keyword Matching**: Matching is case-insensitive and uses SQL `ILIKE` pattern matching for flexible keyword detection.

3. **TRS Score**: Jobs are automatically sorted by TRS score (descending) and then by creation date (newest first).

4. **Pagination**: Use `page` and `page_size` parameters to navigate through results. The response includes `total_pages` to help with pagination UI.

5. **Multiple Categories**: When multiple trade categories are selected, jobs matching ANY of the categories will be returned (OR logic).

6. **Performance**: The endpoint uses database indexes on `country_city`, `state`, and `trs_score` fields for optimal query performance.
