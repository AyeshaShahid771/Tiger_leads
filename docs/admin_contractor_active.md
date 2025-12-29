# Admin — Set Contractor Active (Toggle)

## Overview

Toggle a contractor's active status. The endpoint accepts only the `contractor_id` path parameter and will flip the associated user's `is_active` flag: if the user is active it becomes inactive, and vice versa.

## Endpoint

- Path: `/admin/dashboard/contractors/{contractor_id}/active`
- Method: `PATCH`

## Authentication

- Requires admin authentication (Bearer token or admin API key). Returns `401`/`403` when unauthorized.

## Path Parameters

- `contractor_id` (integer, required) — The ID of the contractor whose account will be toggled.

## Request Body

- None. Do not send a request body — the endpoint will determine the current `is_active` state and flip it.

## Response (200)

Content-Type: `application/json`

Example:

```json
{
  "user_id": 123,
  "is_active": false,
  "message": "Contractor account has been disabled by an administrator."
}
```

## Errors

- `404 Not Found` — Contractor or associated user not found.
- `401 Unauthorized` — Missing or invalid authentication.
- `403 Forbidden` — Authenticated but lacking admin privileges.
- `500 Internal Server Error` — Unexpected server error.

## Notes

- This change removes the requirement to pass `is_active` in the request body; toggling is done unambiguously server-side to prevent race conditions or accidental mismatches.
