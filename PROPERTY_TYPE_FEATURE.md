# Contractor Job Upload Endpoint - Property Type Feature

## Overview
The `/upload-contractor-job` endpoint has been updated to include a **Property Type** field that allows contractors to specify whether a job is **Residential** or **Commercial**.

---

## Endpoint Details

**POST** `/api/jobs/upload-contractor-job`

**Content-Type:** `multipart/form-data`

---

## Request Parameters

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `permit_number` | string | No | Permit identification number |
| `permit_status` | string | No | Current status of the permit |
| `permit_type_norm` | string | No | Normalized permit type |
| `job_address` | string | No | Physical address of the job |
| `project_description` | string | No | Detailed description of the project |
| `project_cost_total` | integer | No | Total project cost |
| `contractor_name` | string | No | Name of the contractor |
| `contractor_company` | string | No | Contractor's company name |
| `contractor_email` | string | No | Contractor's email address |
| `contractor_phone` | string | No | Contractor's phone number |
| `source_county` | string | No | County where the job is located |
| `state` | string | No | State where the job is located |
| **`property_type`** | **string** | **No** | **Property type: "Residential" or "Commercial"** |
| `user_types` | string (JSON) | **Yes** | JSON array of user type configurations |
| `temp_upload_id` | string | No | ID linking to previously uploaded documents |

---

## Property Type Field

### Accepted Values
- `"Residential"` - For residential properties
- `"Commercial"` - For commercial properties
- `null` or omitted - If not specified

### Validation
- If provided, must be exactly `"Residential"` or `"Commercial"`
- Case-sensitive
- Returns 400 error if invalid value is provided

---

## Response Format

### Success Response (200 OK)

```json
{
  "message": "Successfully created 2 job record(s)",
  "job_group_id": "JG-A1B2C3D4E5F6",
  "jobs_created": 2,
  "documents_uploaded": 3,
  "job_ids": [1234, 1235],
  "sample_job": {
    "id": 1234,
    "permit_number": "PMT-2024-12345",
    "job_address": "123 Main Street, Springfield, IL",
    "contractor_name": "John Smith",
    "contractor_company": "ABC Construction",
    "property_type": "Residential",
    "status": "pending"
  }
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `message` | string | Success message with count of created records |
| `job_group_id` | string | Unique ID linking all jobs from this submission |
| `jobs_created` | integer | Number of job records created (one per user type) |
| `documents_uploaded` | integer | Number of documents attached |
| `job_ids` | array | Array of all created job IDs |
| `sample_job` | object | Details of the first created job |
| `sample_job.id` | integer | Job ID |
| `sample_job.permit_number` | string | Permit number |
| `sample_job.job_address` | string | Job address |
| `sample_job.contractor_name` | string | Contractor name |
| `sample_job.contractor_company` | string | Contractor company |
| **`sample_job.property_type`** | **string** | **Property type (Residential/Commercial/null)** |
| `sample_job.status` | string | Job review status (always "pending" for contractor uploads) |

---

## Example Request

```bash
curl -X POST "http://localhost:8000/api/jobs/upload-contractor-job" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "permit_number=PMT-2024-12345" \
  -F "permit_status=Approved" \
  -F "job_address=123 Main Street, Springfield, IL" \
  -F "project_description=Kitchen renovation with new electrical work" \
  -F "project_cost_total=50000" \
  -F "contractor_name=John Smith" \
  -F "contractor_company=ABC Construction" \
  -F "contractor_email=john@abcconstruction.com" \
  -F "contractor_phone=555-1234" \
  -F "source_county=Sangamon" \
  -F "state=Illinois" \
  -F "property_type=Residential" \
  -F 'user_types=[{"user_type":"electrician","offset_days":0},{"user_type":"plumber","offset_days":1}]' \
  -F "temp_upload_id=temp_abc123def456"
```

---

## Database Migration

Run the migration script to add the `property_type` column:

```bash
python add_property_type_column.py
```

This will add:
- Column name: `property_type`
- Data type: `VARCHAR(20)`
- Nullable: Yes
- Allowed values: 'Residential', 'Commercial', or NULL

---

## Changes Made

1. **Database Model** (`src/app/models/user.py`):
   - Added `property_type = Column(String(20), nullable=True)` to Job model

2. **API Endpoint** (`src/app/api/endpoints/jobs.py`):
   - Added `property_type` parameter to function signature
   - Added validation for property_type values
   - Included property_type when creating job records
   - Added property_type to response sample_job object

3. **Migration Script** (`add_property_type_column.py`):
   - Created migration to add property_type column to jobs table

---

## Notes

- Property type is optional and can be left blank
- The field is stored identically for all jobs created from the same submission (same job_group_id)
- All jobs in a job group will have the same property_type value
- Property type can be used for filtering and reporting purposes
