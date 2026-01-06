# Contractor GET & PUT Endpoints

This document documents all GET and PUT endpoints implemented in `src/app/api/endpoints/contractor.py`.

Base path: `/contractor`

Auth & Authorization
- All endpoints use the `get_current_user` dependency and require `Authorization: Bearer <TOKEN>`.
- Most endpoints require the user to have `role == 'Contractor'`. If not, endpoints return HTTP 403.
- Helper `_get_contractor()` enforces role and returns 404 if the contractor profile is missing.

Endpoints (GET / PUT)
---------------------

1) GET `/profile`
- Purpose: Retrieve the authenticated contractor's full `Contractor` model.
- Auth: Required; `role` must be `Contractor`.
- Response (200): full `Contractor` object (Pydantic `ContractorProfile`). Fields include business info, license fields, trade info, location arrays, registration status, file metadata, etc.
- Errors: 403 if not Contractor; 404 if profile missing.

Example curl:

```bash
curl -H "Authorization: Bearer <TOKEN>" https://<API_HOST>/contractor/profile
```

Example response (200):

```json
{
  "id": 21,
  "user_id": 7,
  "company_name": "BuildRight LLC",
  "primary_contact_name": "Alex Smith",
  "phone_number": "555-9876",
  "website_url": "https://buildright.example.com",
  "business_address": "123 Market St, City, ST",
  "business_website_url": "https://www.buildright.com",
  "state_license_number": "LIC-12345",
  "license_expiration_date": "2026-06-30",
  "license_status": "active",
  "license_picture_filename": "license.jpg",
  "referrals_filename": null,
  "job_photos_filename": "jobs.zip",
  "trade_categories": ["General contracting & building"],
  "trade_specialities": ["concrete","framing"],
  "state": ["CA"],
  "country_city": ["Los Angeles, CA"],
  "registration_step": 4,
  "is_completed": true
}
```


2) GET `/account`
- Purpose: Get contractor account info (primary contact name and email).
- Auth: Required; must be Contractor.
- Response (200): `ContractorAccount` with `name` and `email`.

Example curl:

```bash
curl -H "Authorization: Bearer <TOKEN>" https://<API_HOST>/contractor/account
```

Example response (200):

```json
{
  "name": "Alex Smith",
  "email": "alex@buildright.example.com"
}
```

3) PUT `/account`
- Purpose: Update contact name or change password.
- Auth: Required; must be Contractor.
- Request body (`ContractorAccountUpdate`): optional `name`; for password change provide `current_password` and `new_password`.
- Behavior: verifies `current_password` when `new_password` provided, updates user password hash.
- Response (200): updated `ContractorAccount`.
- Errors: 400 if `current_password` incorrect.

Example curl (change name):

```bash
curl -X PUT -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{"name":"Alexander Smith"}' \
  https://<API_HOST>/contractor/account
```

Example success response (200):

```json
{
  "name": "Alexander Smith",
  "email": "alex@buildright.example.com"
}
```


4) GET `/business-details`
- Purpose: Retrieve primary business details.
- Auth: Required; must be Contractor.
- Response (200): `ContractorBusinessDetails` with `company_name`, `phone_number`, `business_address`, `business_website_url`.

Example response (200):

```json
{
  "company_name": "BuildRight LLC",
  "phone_number": "555-9876",
  "business_address": "123 Market St, City, ST",
  "business_website_url": "https://www.buildright.com"
}
```

5) PUT `/business-details`
- Purpose: Update business details.
- Auth: Required; must be Contractor.
- Request body (`ContractorBusinessDetailsUpdate`): optional fields matching the response.
- Response (200): updated `ContractorBusinessDetails`.

Example request (curl):

```bash
curl -X PUT -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{"company_name":"BuildRight LLC","phone_number":"555-9876","business_address":"123 Market St"}' \
  https://<API_HOST>/contractor/business-details
```

Example success response (200):

```json
{
  "company_name": "BuildRight LLC",
  "phone_number": "555-9876",
  "business_address": "123 Market St, City, ST",
  "business_website_url": "https://www.buildright.com"
}
```


6) GET `/license-info`
- Purpose: Retrieve license metadata (number, expiry, status, filename).
- Auth: Required; must be Contractor.
- Response (200): `ContractorLicenseInfo` with `state_license_number`, `license_expiration_date`, `license_status`, `license_picture_filename`.

Example response (200):

```json
{
  "state_license_number": "LIC-12345",
  "license_expiration_date": "2026-06-30",
  "license_status": "active",
  "license_picture_filename": "license.jpg"
}
```

7) PUT `/license-info`
- Purpose: Update license fields (number, expiration date, status).
- Auth: Required; must be Contractor.
- Request body (`ContractorLicenseInfoUpdate`): optional `state_license_number`, `license_expiration_date`, `license_status`.
- Response (200): updated `ContractorLicenseInfo`.

Example request (curl):

```bash
curl -X PUT -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{"state_license_number":"LIC-67890","license_expiration_date":"2027-08-31","license_status":"active"}' \
  https://<API_HOST>/contractor/license-info
```

Example success response (200):

```json
{
  "state_license_number": "LIC-67890",
  "license_expiration_date": "2027-08-31",
  "license_status": "active",
  "license_picture_filename": "license.jpg"
}
```


8) GET `/trade-info`
- Purpose: Retrieve trade categories and specialities.
- Auth: Required; must be Contractor.
- Response (200): `ContractorTradeInfo` with `trade_categories` (array) and `trade_specialities` (array).

Example response (200):

```json
{
  "trade_categories": ["General contracting & building"],
  "trade_specialities": ["concrete","framing"]
}
```

9) PUT `/trade-info`
- Purpose: Update trade categories and specialities.
- Auth: Required; must be Contractor.
- Request body (`ContractorTradeInfoUpdate`): optional `trade_categories`, `trade_specialities`.
- Response (200): updated `ContractorTradeInfo`.

Example request (curl):

```bash
curl -X PUT -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{"trade_categories":["General contracting & building"],"trade_specialities":["concrete","framing"]}' \
  https://<API_HOST>/contractor/trade-info
```

Example success response (200):

```json
{
  "trade_categories": ["General contracting & building"],
  "trade_specialities": ["concrete","framing"]
}
```


10) GET `/location-info`
- Purpose: Retrieve service jurisdictions: `state` and `country_city` arrays.
- Auth: Required; must be Contractor.
- Response (200): `ContractorLocationInfo`.

Example response (200):

```json
{
  "state": ["CA"],
  "country_city": ["Los Angeles, CA"]
}
```

11) PUT `/location-info`
- Purpose: Update service jurisdictions.
- Auth: Required; must be Contractor.
- Request body (`ContractorLocationInfoUpdate`): optional `state` (single string) and `country_city` (single string). Server stores them as single-element arrays.
- Response (200): updated `ContractorLocationInfo`.

Example request (curl):

```bash
curl -X PUT -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{"state":"CA","country_city":"Los Angeles, CA"}' \
  https://<API_HOST>/contractor/location-info
```

Example success response (200):

```json
{
  "state": ["CA"],
  "country_city": ["Los Angeles, CA"]
}
```

Notes & Implementation details
- Role check: `_require_contractor()` ensures only Contractor-role users access these endpoints.
- Contractor lookup: `_get_contractor()` fetches the `models.user.Contractor` record by `current_user.id` and returns 404 if missing.
- File uploads for Step 2 are handled via multipart/form-data in `/step-2` (POST) and store file contents and filenames on the model; those endpoints are not GET/PUT and thus are not covered in this document.
- Password changes in `/account` use `verify_password()` and `hash_password()`.

Related files
- Endpoint implementation: `src/app/api/endpoints/contractor.py`
- Schemas: `src/app/schemas/contractor.py` (request/response types)
- Models: `src/app/models/user.py` (Contractor model)

**Auth Endpoints**

12) GET `/user/profile`
- Purpose: Retrieve the authenticated user's basic account info (primary contact name and email).
- Auth: Required; uses the `get_current_user` dependency and requires a valid `Authorization: Bearer <TOKEN>`.
- Response (200): JSON object with `name` and `email`.
- Errors: 401 if authentication is missing or token is invalid.

Example curl:

```bash
curl -H "Authorization: Bearer <TOKEN>" https://<API_HOST>/user/profile
```

Example response (200):

```json
{
  "name": "Alex Smith",
  "email": "alex@buildright.example.com"
}
```

13) POST `/logout`
- Purpose: Revoke the current user's authentication token / perform logout.
- Auth: Required; uses the `get_current_user` dependency.
- Behavior: Invalidates the token on the server side (if the app stores active tokens) or otherwise signals the client to delete the token. Implementation details depend on the app's token strategy.
- Response (204): no content on successful logout.
- Errors: 401 if the request is unauthenticated.

Example curl:

```bash
curl -X POST -H "Authorization: Bearer <TOKEN>" https://<API_HOST>/logout
```

Example success response (204): empty body

Notes
- These auth endpoints are general and may be implemented in your main auth/router module rather than the contractor-specific endpoints file.
- If you want, I can add exact schema names and server-side behavior based on how tokens are stored (JWT stateless vs. server-side sessions/blacklist).

Next steps
- I can add schema-accurate example payloads using `src/app/schemas/contractor.py` or include error-case responses (403/400/404). Which would you like next?
