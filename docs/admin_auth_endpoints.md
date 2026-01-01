# Admin Authentication Endpoints

Reference for the admin authentication endpoints that operate against the `admin_users` table.

## Overview
- These endpoints manage admin signup, verification, login/token issuance, logout, profile, account updates, and password reset flows.
- Protected endpoints require an admin JWT (issued by the API). Role-restricted dashboard endpoints use `require_admin_or_editor` (admin or editor) or `require_admin_only` (admin only); the endpoints documented here are primarily self-service for any active admin.

---

## Conventions
- All timestamps are UTC.
- Password hashing: bcrypt (passwords truncated to 72 bytes before hashing).
- Tokens include `iat` (issued-at). Token validation compares `iat` to `admin_users.last_logout_at` when present; tokens with `iat` ≤ `last_logout_at` are rejected.

---

## POST /admin/auth/signup
- Description: Start signup for an existing `admin_users` email; generates a verification code and (optionally) stores a password hash.
- Auth: none
- Allowed admin roles: N/A (no auth; used to set password for existing admin_users row)
- Request JSON (schema: `UserCreate`)

```json
{
  "email": "admin@example.com",
  "password": "hunter2"
}
```

- Response (200):

```json
{ "message": "Verification code sent to admin email", "email": "admin@example.com" }
```

- Notes: `verification_code` and `code_expires_at` are stored on the `admin_users` row.

---

## POST /admin/auth/verify/{email}
- Description: Complete signup by validating the verification code; activates the admin and returns an access token.
- Auth: none
- Allowed admin roles: N/A (no auth; completes signup for an admin_users row)
- Request JSON (schema: `VerifyEmail`)

```json
{ "code": "123456" }
```

- Response (200):

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "message": "Admin verified and activated",
  "admin_user_id": 8
}
```

- Notes: Sets `is_active = true` and clears the verification code fields.

---

## POST /admin/auth/login
- Description: Login using JSON body (email + password). Issues a JWT.
- Auth: none
- Allowed admin roles: Any active admin (all roles may log in)
- Request JSON (schema: `UserLogin`)

```json
{ "email": "admin@example.com", "password": "hunter2" }
```

- Response (200):

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "message": "Admin login successful",
  "admin_user_id": 8
}
```

- Notes: Any active admin can login; token contains `sub` (email), `admin_user_id`, and `iat`.

---

## POST /admin/auth/token
- Description: OAuth2 Password token endpoint used by OpenAPI "Authorize" lock and programmatic flows. Accepts form-encoded `username` and `password`.
- Auth: none
- Allowed admin roles: Any active admin (all roles may obtain a token)
- Request (form): `username`, `password` (OAuth2 Password grant form)
- Response (200):

```json
{ "access_token": "<jwt>", "token_type": "bearer", "admin_user_id": 8 }
```

- Notes: Mirrors `/admin/auth/login` so the docs UI can obtain tokens.

---

## POST /admin/auth/logout
- Description: Record `last_logout_at` for the calling admin to support token revocation semantics.
- Auth: Bearer admin token (`require_admin_token`)
- Allowed admin roles: Any active admin (all roles may call logout for their account)
- Request: none
- Response (200):

```json
{ "message": "Logged out" }
```

- Behavior:
  - Ensures the `last_logout_at` column exists on `admin_users` (creates it if missing).
  - Sets `last_logout_at = now()` for the calling admin row.
  - Token validation rejects tokens with `iat` ≤ `last_logout_at`.

---

## GET /admin/auth/profile
- Description: Return authenticated admin's profile (id, email, name).
- Auth: Bearer admin token (`require_admin_token`)
- Allowed admin roles: Any active admin (returns the profile for the authenticated admin)
- Request: none
- Response (200):

```json
{ "id": 8, "email": "admin@example.com", "name": "Admin Name" }
```

- Notes: Returns profile for the authenticated admin only.

---

## PUT /admin/auth/account
- Description: Update the authenticated admin's `name` and/or change password.
- Auth: Bearer admin token (`require_admin_token`)
- Allowed admin roles: Any active admin (may update their own account)
- Request JSON (schema: `AdminAccountUpdate`)

```json
{
  "name": "New Admin",
  "current_password": "oldpass",
  "new_password": "newpass"
}
```

- Response (200):

```json
{ "message": "Account updated", "id": 8, "email": "admin@example.com" }
```

- Behavior and rules:
  - If `new_password` is provided, `current_password` is required.
  - `current_password` is verified using `verify_password()` (bcrypt check with 72-byte truncation). If verification fails, response is 401.
  - When changing password, the new password is hashed with `hash_password()` (bcrypt) and saved to `password_hash`.
  - The handler updates `name` and/or `password_hash` atomically.
  - Current implementation does NOT automatically update `last_logout_at` on password change. Recommended: update `last_logout_at = now()` when password changes to immediately revoke existing tokens; I can add this behavior.

---

## POST /admin/auth/forgot-password
- Description: Initiate password reset flow for an admin; stores a `reset_token` and expiry on `admin_users` and sends a reset link.
- Auth: none
- Allowed admin roles: N/A (no auth; initiates reset for an admin_users email)
- Request JSON (schema: `PasswordResetRequest`)

```json
{ "email": "admin@example.com" }
```

- Response (200):

```json
{ "message": "Password reset link sent to admin email" }
```

---

## POST /admin/auth/reset-password
- Description: Confirm reset using the stored token and set a new password.
- Auth: none
- Allowed admin roles: N/A (no auth; completes reset using stored reset_token)
- Request JSON (schema: `PasswordResetConfirm`)

```json
{ "token": "<token>", "new_password": "newpass" }
```

- Response (200):

```json
{ "message": "Admin password updated successfully" }
```

- Notes: Token lookup uses `admin_users.reset_token` and respects `reset_token_expires_at`.

---

## Role Mapping & Who Can Use What
- Endpoints above are primarily for self-service and require the caller to be the admin they operate on (authenticated via token). Any active admin may call `profile`, `account`, and `logout` for themselves.
- Dashboard and management endpoints (separate module `/admin/dashboard`) use role-based dependencies:
  - `require_admin_or_editor` — allows `admin` and `editor` roles.
  - `require_admin_only` — allows `admin` only.
- If you want a list of which `/admin/dashboard` routes use which dependency, I can generate a mapping and add it to the docs.

---

## Testing (quick)
1. Start server:

```bash
uvicorn src.app.main:app --reload
```

2. Obtain token (via docs lock or curl):

```bash
curl -X POST -d "username=admin@example.com&password=secret" http://localhost:8000/admin/auth/token
```

3. Call protected endpoint with header:

```bash
curl -H "Authorization: Bearer <TOKEN>" http://localhost:8000/admin/auth/profile
```

4. Change password and (optional) revoke tokens by updating `last_logout_at`:

```bash
curl -X PUT -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{"current_password":"old","new_password":"new"}' http://localhost:8000/admin/auth/account
```

---

## Implementation notes & recommendations
- Enforce `last_logout_at` on password change to immediately revoke old tokens. I can patch `PUT /admin/auth/account` to set `last_logout_at = now()` when `new_password` is used.
- Consider setting `JWT_ACCESS_TOKEN_EXPIRE_HOURS` to a modest value (1-8 hours) to limit exposure if token revocation is delayed.
- For per-token revocation, consider adding `jti` to tokens and a `revoked_tokens` table or Redis set.

---

If you want this file moved into another location or adjusted to use the project's existing docs template, tell me where and I'll adapt it.