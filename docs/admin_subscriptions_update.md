Admin: Update Subscriptions Endpoint

Endpoint: PATCH /admin/dashboard/subscriptions
Requires: Admin bearer token (use the Admin Authorize in Swagger or `Authorization: Bearer <ADMIN_TOKEN>` header)

Purpose
- Bulk update subscription plan fields (Starter, Professional, Enterprise, Custom).

Request JSON formats accepted

1) Bulk plans array (recommended)
- Content-Type: application/json
- Body: an object with a `plans` array. Each item describes one plan to update.

Example:
{
  "plans": [
    {"name":"Starter", "price":"9.99", "credits":10, "max_seats":1},
    {"name":"Professional", "price":"29.99", "credits":50, "max_seats":3},
    {"name":"Enterprise", "price":"99.99", "credits":200, "max_seats":10},
    {"name":"Custom", "credit_price":"0.10", "seat_price":"9.99"}
  ]
}

Field descriptions
- name (string) — Plan name to match in the `subscriptions.name` column. Expected values: `Starter`, `Professional`, `Enterprise`, `Custom`.
- price (string) — Monthly plan price (stored as string in DB). Provide as numeric string, e.g. "9.99".
- credits (integer) — Number of monthly credits for the plan (applies to Starter/Professional/Enterprise).
- max_seats (integer) — Maximum seats allowed for the plan.
- credit_price (string) — (Custom plan only) per-credit price override for Custom plans, e.g. "0.10".
- seat_price (string) — (Custom plan only) per-seat price override for Custom plans, e.g. "9.99".

Behavior
- The endpoint locates subscription rows by `subscriptions.name` and updates only supplied fields.
- Unknown plan names are ignored (they are skipped). The endpoint returns an `updated` array describing the rows changed.
- Values are written as provided; no complex validation is performed by the endpoint (recommended: pass properly formatted numeric strings for currency fields).

Response
- 200 OK with JSON: { "updated": [ { "name": "Starter", "price": "9.99", "credits": 10, "max_seats": 1, "credit_price": null, "seat_price": null }, ... ] }

Errors
- 401/403 when the caller is not authorized as admin.
- The endpoint will not return 400 for unknown plan names; those entries are skipped. If you want stricter validation, request that behavior and it can be added.

Examples (curl)

curl -X PATCH "http://localhost:8000/admin/dashboard/subscriptions" \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "plans": [
      {"name":"Starter","price":"9.99","credits":10,"max_seats":1},
      {"name":"Custom","credit_price":"0.10","seat_price":"9.99"}
    ]
  }'

Notes
- If you prefer single-plan updates, send a `plans` array with a single item.
- Consider adding audit logging (who changed what) for production safety — I can add that if you want.
