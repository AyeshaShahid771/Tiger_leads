# Admin dashboard endpoints

All endpoints below require an authenticated user with the `admin_user` role. Authentication is via bearer token (e.g. `Authorization: Bearer <token>`). Responses use JSON. Common errors: `401 Unauthorized`, `403 Forbidden` (not an admin), `404 Not Found`, `422 Unprocessable Entity` (validation).

---

**GET /admin/dashboard/jobs/{job_id}** — Get Job Details (Admin)

- **Description:** Return full details for a single job for admin review (including supplier/contractor, status, metadata and ingestion source).
- **Access:** `admin_user` (recommended enforcement: `require_admin_or_editor` if editors may view)
- **Path params:**
  - `job_id` (string|int) — job identifier.
- **Request:**
  - Headers: `Authorization: Bearer <token>`
- **Response (200):**

```json
{
  "id": 12345,
  "title": "Plumbing repair",
  "description": "Fix burst pipe in basement",
  "status": "active",
  "posted_at": "2025-12-01T12:34:56Z",
  "contractor_id": 987,
  "supplier": {"id": 42, "name": "Supplier Co"},
  "location": {"city":"Austin","state":"TX","zipcode":"78701"},
  "meta": {"source":"ingest","external_id":"ext-abc-123"}
}
```

- **Errors:** `404` if job not found, `403` if not admin.

---

**POST /admin/dashboard/filter** — Admin Dashboard Filter

- **Description:** Run a dashboard query with filters and pagination. Used by the admin UI to fetch filtered job lists, contractor summaries or time-series snippets depending on the filter payload.
- **Access:** `admin_user`
- **Request body (application/json):**

```json
{
  "resource": "jobs",                 // required: "jobs" | "contractors" | "ingested_jobs"
  "filters": {
    "status": ["active","closed"],
    "date_from": "2025-11-01",
    "date_to": "2025-12-31",
    "contractor_id": 987,
    "search": "plumb",
    "source": "ingest"
  },
  "sort": {"field":"posted_at","dir":"desc"},
  "page": 1,
  "per_page": 25
}
```

- **Response (200):** Returns a paginated result keyed by the requested `resource`. Example for `jobs`:

```json
{
  "resource": "jobs",
  "total": 142,
  "page": 1,
  "per_page": 25,
  "items": [ /* array of job summaries */ ]
}
```

- **Errors:** `422` for invalid filters, `403` if not admin.

---

**GET /admin/dashboard** — Admin Dashboard

- **Description:** Top-level dashboard data for admin landing page: global counts, key metrics, and light time-series for charts (jobs posted, conversions, revenue if applicable).
- **Access:** `admin_user`
- **Query params (optional):**
  - `date_from` (YYYY-MM-DD)
  - `date_to` (YYYY-MM-DD)
  - `granularity` (`day`|`week`|`month`)
- **Response (200):**

```json
{
  "counts": {
    "total_jobs": 1024,
    "active_jobs": 312,
    "ingested_pending": 12,
    "contractors": 210
  },
  "trends": {
    "jobs_posted": [{"date":"2025-12-01","count":12}, {"date":"2025-12-02","count":8}],
    "leads": [{"date":"2025-12-01","count":48}]
  },
  "top_contractors": [{"contractor_id":987,"name":"ACME","jobs":24}]
}
```

- **Errors:** `403` if not admin.

---

**GET /admin/dashboard/contractors-summary** — Contractors Summary

- **Description:** Aggregated metrics for contractors (counts, average response time, jobs completed, active contracts). Useful for listing and sorting contractor performance.
- **Access:** `admin_user`
- **Query params:**
  - `page`, `per_page`, `sort_field`, `sort_dir`, `min_jobs`
- **Response (200):**

```json
{
  "total": 210,
  "page": 1,
  "per_page": 25,
  "items": [
    {"contractor_id": 987, "name": "ACME", "jobs_completed": 124, "avg_response_mins": 42},
    {"contractor_id": 988, "name": "Beta Co", "jobs_completed": 88, "avg_response_mins": 30}
  ]
}
```

- **Errors:** `403` if not admin.

---

**GET /admin/dashboard/ingested-jobs** — Job Posted Requested (Ingested Jobs)

- **Description:** Return a list of jobs that were ingested from external sources and await admin review (e.g. to post or decline).
- **Access:** `admin_user`
- **Query params:**
  - `status` (optional) — `pending`|`posted`|`declined`
  - `page`, `per_page`, `search`, `source`
- **Response (200):**

```json
{
  "total": 12,
  "page": 1,
  "per_page": 25,
  "items": [
    {"id": 555,"title":"AC repair","source":"ingest","received_at":"2025-12-28T10:00:00Z","status":"pending"}
  ]
}
```

- **Errors:** `403` if not admin.

---

**PATCH /admin/dashboard/ingested-jobs/{job_id}/post** — Post Ingested Job

- **Description:** Mark an ingested job as posted to the live jobs feed (admin approves and publishes the job). This transitions job from `ingested_pending` to `posted`/`active` and may trigger notifications.
- **Access:** `admin_user`
- **Path params:** `job_id` (string|int)
- **Request body (optional):**
  - `override_fields` (object) — optional fields to override before posting (e.g. adjusted price, corrected location)

Example request body:

```json
{ "override_fields": { "price": 150.0, "location": {"city":"Dallas","state":"TX"} } }
```

- **Response (200):** Updated job object

```json
{
  "id": 555,
  "status": "active",
  "posted_at": "2025-12-31T13:00:00Z"
}
```

- **Errors:** `404` if job not found, `409` if job already posted, `403` if not admin.

---

**PATCH /admin/dashboard/ingested-jobs/{job_id}/decline** — Decline Ingested Job

- **Description:** Decline an ingested job; record a reason and set status to `ingested_declined`. This keeps a record for auditing and optionally notifies the source.
- **Access:** `admin_user`
- **Path params:** `job_id` (string|int)
- **Request body (application/json):**

```json
{
  "reason": "Duplicate listing",
  "notify_source": true
}
```

- **Response (200):**

```json
{
  "id": 555,
  "status": "ingested_declined",
  "declined_at": "2025-12-31T13:05:00Z",
  "reason": "Duplicate listing"
}
```

- **Errors:** `404` if job not found, `403` if not admin.

---

If you want, I can add concrete JSON Schema definitions for request/response bodies, `curl` examples for each endpoint, or indicate which endpoints should allow `editor` as well as `admin`. Which would you like next?
# Admin Dashboard Endpoints

Documentation for admin dashboard routes (paths, methods, request/response examples, and which `admin_users` roles can call each).

Notes:
- All admin endpoints are prefixed with `/admin/dashboard` and use admin-specific dependencies.
- Role enforcement: use `require_admin_or_editor` to allow `admin` and `editor` roles, and `require_admin_only` to restrict to `admin` only. Where noted below, the endpoint required roles are indicated.

---

## GET /admin/dashboard/jobs/{job_id} — Get Job Details (Admin)
- Description: Return details for a job visible in the admin dashboard.
- Method: GET
- Path params:
  - `job_id` (integer)
- Request: none
- Response (200): Example JSON (fields depend on jobs model):
```json
{
  "id": 123,
  "title": "Plumber needed",
  "description": "Fix a leaky pipe",
  "status": "published",
  "supplier_id": 45,
  "created_at": "2025-12-31T12:00:00Z"
}
```
- Allowed admin roles: `admin` or `editor` (recommended: `require_admin_or_editor`).

---

## POST /admin/dashboard/filter — Admin Dashboard Filter
- Description: Apply filters and return dashboard metrics or lists (paginated).
- Method: POST
- Request JSON (example):
```json
{ "query": { "status": "open", "role": "contractor" }, "page": 1, "per_page": 25 }
```
- Response (200):
```json
{ "total": 42, "page": 1, "per_page": 25, "items": [ /* jobs/users summary */ ] }
```
- Allowed admin roles: `admin` or `editor`.

---

## GET /admin/dashboard — Admin Dashboard
- Description: Return main dashboard summary and key metrics.
- Method: GET
- Request: none (optional query parameters for date ranges)
- Response (200): Example:
```json
{ "open_jobs": 120, "pending_ingested_jobs": 5, "active_suppliers": 430 }
```
- Allowed admin roles: `admin` or `editor`.

---

## GET /admin/dashboard/contractors-summary — Contractors Summary
- Description: Summary metrics for contractors (counts by region, status, etc.)
- Method: GET
- Response (200): Example:
```json
{ "total": 1000, "active": 800, "by_state": { "CA": 200, "NY": 150 } }
```
- Allowed admin roles: `admin` or `editor`.

---

## GET /admin/dashboard/ingested-jobs — Job Posted Requested
- Description: List ingested jobs awaiting review (pending/declined/state).
- Method: GET
- Response (200): list of ingested job objects
- Allowed admin roles: `admin` or `editor`.

---

## PATCH /admin/dashboard/ingested-jobs/{job_id}/post — Post Ingested Job
- Description: Convert an ingested (pending) job into a published job.
- Method: PATCH
- Path params: `job_id` (integer)
- Request JSON (optional): may include fields to override before posting
- Response (200): `{ "message": "Job posted", "job_id": 123 }`
- Allowed admin roles: `admin` or `editor`.

---

## PATCH /admin/dashboard/ingested-jobs/{job_id}/decline — Decline Ingested Job
- Description: Mark an ingested job as declined with optional reason.
- Method: PATCH
- Request JSON example:
```json
{ "reason": "Duplicate or invalid data" }
```
- Response (200): `{ "message": "Ingested job declined" }`
- Allowed admin roles: `admin` or `editor`.

---

## GET /admin/dashboard/ingested-jobs/system — System-ingested Jobs
- Description: List system-ingested jobs (internal/automated sources).
- Method: GET
- Response: list of system-ingested job objects
- Allowed admin roles: `admin` or `editor`.

---

## DELETE /admin/dashboard/ingested-jobs/{job_id} — Delete Ingested Job
- Description: Permanently delete an ingested job entry.
- Method: DELETE
- Response (200): `{ "message": "Ingested job deleted" }`
- Allowed admin roles: `admin` only (recommended `require_admin_only`).

---

## PATCH /admin/dashboard/subscriptions — Update Subscriptions
- Description: Apply bulk subscription plan updates or modify a subscription record.
- Method: PATCH
- Request JSON (example):
```json
{ "subscription_id": 55, "plan": "enterprise", "seats": 25 }
```
- Response (200): `{ "message": "Subscription updated" }`
- Allowed admin roles: `admin` only.

---

## GET /admin/dashboard/suppliers-summary — Suppliers Summary
- Description: Summary metrics for suppliers.
- Method: GET
- Response example:
```json
{ "total": 500, "active": 420, "by_country": { "US": 300 } }
```
- Allowed admin roles: `admin` or `editor`.

---

## GET /admin/dashboard/admin-users/recipients — Admin Users Recipients
- Description: Return non-admin admin_users suitable as email recipients (status: active|invited)
- Method: GET
- Response example:
```json
[ { "id": 10, "name": "Alice", "email": "a@example.com", "role": "manager", "status": "active" } ]
```
- Allowed admin roles: `admin` only (sensitive user list).

---

## GET /admin/dashboard/admin-users/by-role — Admin Users By Role
- Description: List admin_users filtered by role (excluding `admin` role in results)
- Method: GET
- Query params: `role` (string)
- Response example:
```json
[ { "id": 11, "name": "Bob", "email": "b@example.com", "role": "editor", "status": "active" } ]
```
- Allowed admin roles: `admin` only.

---

## GET /admin/dashboard/admin-users/search — Admin Users Search
- Description: Search admin_users by name or email (case-insensitive)
- Method: GET
- Query params: `q` (string)
- Response: list of matching admin_users
- Allowed admin roles: `admin` only.

---

## DELETE /admin/dashboard/admin-users/{admin_id} — Delete Admin User
- Description: Remove an admin_users entry (careful: destructive)
- Method: DELETE
- Path params: `admin_id` (integer)
- Response (200): `{ "message": "Admin user deleted" }`
- Allowed admin roles: `admin` only.

---

## POST /admin/dashboard/admin-users/invite — Invite Admin User
- Description: Create a pending admin user entry (is_active=false) and send invitation email with verification link.
- Method: POST
- Request JSON (example):
```json
{ "email": "newadmin@example.com", "name": "New Admin", "role": "editor" }
```
- Response (201): `{ "message": "Invitation created", "email": "newadmin@example.com" }`
- Allowed admin roles: `admin` only (inviting admins is privileged).

---

## GET /admin/dashboard/contractors/{contractor_id} — Contractor Detail
- Description: Return contractor details including profile fields used in dashboard.
- Method: GET
- Response example:
```json
{ "id": 200, "name": "ACME Corp", "active": true, "jobs_posted": 12 }
```
- Allowed admin roles: `admin` or `editor`.

---

## GET /admin/dashboard/suppliers/{supplier_id} — Supplier Detail
- Description: Supplier full detail for dashboard.
- Method: GET
- Response example:
```json
{ "id": 45, "name": "SupplyCo", "country": "US", "active": true }
```
- Allowed admin roles: `admin` or `editor`.

---

## GET /admin/dashboard/contractors/{contractor_id}/image/{field} — Contractor Image
- Description: Retrieve contractor image by `field` name (e.g., `logo`, `profile_image`).
- Method: GET
- Path params:
  - `contractor_id` (int)
  - `field` (string)
- Response: binary image stream or redirect to storage URL
- Allowed admin roles: `admin` or `editor`.

---

## PATCH /admin/dashboard/contractors/{contractor_id}/active — Set Contractor Active
- Description: Toggle contractor `is_active` flag.
- Method: PATCH
- Request JSON example: `{ "active": true }`
- Response (200): `{ "message": "Contractor updated", "id": 200 }`
- Allowed admin roles: `admin` only.

---

## PATCH /admin/dashboard/suppliers/{supplier_id}/active — Set Supplier Active
- Description: Toggle supplier `is_active` flag.
- Method: PATCH
- Request JSON example: `{ "active": false }`
- Response (200): `{ "message": "Supplier updated", "id": 45 }`
- Allowed admin roles: `admin` only.

---

## Testing & Notes
- Use the admin OpenAPI lock (Authorize) to obtain a token via `/admin/auth/token`.
- For endpoints that modify data (`POST`, `PATCH`, `DELETE`), test with a user that has the `admin` role unless the endpoint explicitly allows `editor`.
- Request/response shapes above are examples — consult the route implementations if you need exact fields.

---

If you want, I can:
- Generate a CSV or markdown table mapping each `/admin/dashboard` route to the exact dependency used (`require_admin_only` or `require_admin_or_editor`) by scanning the code and producing the mapping automatically.
- Add concrete request/response Pydantic schema links where available.
