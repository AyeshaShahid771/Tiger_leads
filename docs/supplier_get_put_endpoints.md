# Supplier GET & PUT Endpoints

This document documents all GET and PUT endpoints implemented in `src/app/api/endpoints/supplier.py`.

Base path: `/supplier`

Auth & Authorization
- All endpoints use the `get_current_user` dependency and require an Authorization header: `Authorization: Bearer <TOKEN>`.
- Most endpoints require the user to have `role == 'Supplier'`. If the user is not a Supplier, endpoints return HTTP 403.
- Helper `_get_supplier()` fetches the `Supplier` record by `current_user.id` and returns 404 if missing.

Endpoints (GET / PUT)
---------------------

1) GET `/profile`
- Purpose: Retrieve the authenticated supplier's full profile.
- Auth: Required; `role` must be `Supplier`.
- Response (200): `SupplierProfile` object with fields such as:
  - `id`, `user_id`, `company_name`, `primary_contact_name`, `phone_number`, `website_url`, `years_in_business`, `business_type`,
  - `service_states`, `country_city`, `onsite_delivery`, `delivery_lead_time`,
  - `carries_inventory`, `offers_custom_orders`, `minimum_order_amount`, `accepts_urgent_requests`, `offers_credit_accounts`,
  - `product_categories`, `product_types`, `registration_step`, `is_completed`.
- Errors: 403 if not Supplier; 404 if supplier profile not found.

Example curl:

```bash
curl -H "Authorization: Bearer <TOKEN>" https://<API_HOST>/supplier/profile
```
 
 Example response (200):

 ```json
 {
   "id": 12,
   "user_id": 5,
   "company_name": "Acme Builders",
   "primary_contact_name": "Jane Doe",
   "phone_number": "555-1234",
   "website_url": "https://acme.example.com",
   "years_in_business": 10,
   "business_type": "LLC",
   "service_states": ["CA","NV"],
   "country_city": ["San Francisco, CA"],
   "onsite_delivery": "yes",
   "delivery_lead_time": "3-5 days",
   "carries_inventory": "yes",
   "offers_custom_orders": "no",
   "minimum_order_amount": 100,
   "accepts_urgent_requests": "yes",
   "offers_credit_accounts": "no",
   "product_categories": "Flooring",
   "product_types": ["Tile","Hardwood"],
   "registration_step": 4,
   "is_completed": true
 }
 ```


2) GET `/account`
- Purpose: Get supplier account info (name, email).
- Auth: Required; must be Supplier and have a supplier record.
- Response (200): `SupplierAccount` object:
  - `name` (primary contact name), `email` (user email).

Example curl:

```bash
curl -H "Authorization: Bearer <TOKEN>" https://<API_HOST>/supplier/account
```

Example response (200):

```json
{
  "name": "Jane Doe",
  "email": "jane@acme.example.com"
}
```

3) PUT `/account`
- Purpose: Update supplier account details: change name or change password.
- Auth: Required; must be Supplier.
- Request body (JSON): `SupplierAccountUpdate` fields:
  - `name` (optional): new primary contact name.
  - `current_password` (required when changing password), `new_password` (optional): password change flow.
- Behaviour: If `new_password` provided, server verifies `current_password` against stored hash; on success updates `current_user.password_hash`.
- Success response (200): updated `SupplierAccount` with `name` and `email`.
- Errors: 400 if `current_password` is incorrect when changing password; 403/404 as above.

Example curl (change name):

```bash
curl -X PUT -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{"name":"New Contact Name"}' \
  https://<API_HOST>/supplier/account
```

Example success response (200):

```json
{
  "name": "New Contact Name",
  "email": "jane@acme.example.com"
}
```

Example curl (change password):

```bash
curl -X PUT -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{"current_password":"oldpass","new_password":"newpass123"}' \
  https://<API_HOST>/supplier/account
```

Example success response (200):

```json
{
  "name": "Jane Doe",
  "email": "jane@acme.example.com"
}
```


4) GET `/business-details`
- Purpose: Retrieve basic business details.
- Auth: Required; must be Supplier.
- Response (200): `SupplierBusinessDetails`:
  - `company_name`, `phone_number`, `business_type`, `years_in_business`.

Example curl:

```bash
curl -H "Authorization: Bearer <TOKEN>" https://<API_HOST>/supplier/business-details
```

Example response (200):

```json
{
  "company_name": "Acme Builders",
  "phone_number": "555-1234",
  "business_type": "LLC",
  "years_in_business": 10
}
```

5) PUT `/business-details`
- Purpose: Update business details.
- Auth: Required; must be Supplier.
- Request body (JSON): `SupplierBusinessDetailsUpdate` fields (all optional):
  - `company_name`, `phone_number`, `business_type`, `years_in_business`.
- Response (200): updated `SupplierBusinessDetails` JSON.

Example curl:

```bash
curl -X PUT -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{"company_name":"Acme Builders","phone_number":"555-1234"}' \
  https://<API_HOST>/supplier/business-details
```

Example success response (200):

```json
{
  "company_name": "Acme Builders",
  "phone_number": "555-1234",
  "business_type": "LLC",
  "years_in_business": 10
}
```


6) GET `/delivery-info`
- Purpose: Retrieve delivery & service-area data.
- Auth: Required; must be Supplier.
- Response (200): `SupplierDeliveryInfo`:
  - `service_states` (array), `country_city` (array), `onsite_delivery` ("yes"/"no"), `delivery_lead_time`.

Example curl:

```bash
curl -H "Authorization: Bearer <TOKEN>" https://<API_HOST>/supplier/delivery-info
```

Example response (200):

```json
{
  "service_states": ["CA","NV"],
  "country_city": ["San Francisco, CA"],
  "onsite_delivery": "yes",
  "delivery_lead_time": "3-5 days"
}
```

7) PUT `/delivery-info`
- Purpose: Update service area & delivery details.
- Auth: Required; must be Supplier.
- Request body (JSON): `SupplierDeliveryInfoUpdate` fields (all optional):
  - `service_states` (array of state codes/names),
  - `country_city` (single string; server stores as array with the single item),
  - `onsite_delivery` (string; accepted values are `yes`/`no` or `true`/`false` — server normalizes with `_normalize_yes_no`),
  - `delivery_lead_time`.
- Response (200): updated `SupplierDeliveryInfo`.
- Errors: 400 if `onsite_delivery` cannot be normalized to yes/no.

Example curl:

```bash
curl -X PUT -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{"service_states":["CA","NV"],"country_city":"San Francisco, CA","onsite_delivery":"yes","delivery_lead_time":"3-5 days"}' \
  https://<API_HOST>/supplier/delivery-info
```

Example success response (200):

```json
{
  "service_states": ["CA","NV"],
  "country_city": ["San Francisco, CA"],
  "onsite_delivery": "yes",
  "delivery_lead_time": "3-5 days"
}
```


8) GET `/capabilities`
- Purpose: Retrieve supplier capabilities and options.
- Auth: Required; must be Supplier.
- Response (200): `SupplierCapabilities` with fields:
  - `carries_inventory` ("yes"/"no"), `offers_custom_orders` ("yes"/"no"), `minimum_order_amount`, `accepts_urgent_requests` ("yes"/"no"), `offers_credit_accounts` ("yes"/"no").

Example curl:

```bash
curl -H "Authorization: Bearer <TOKEN>" https://<API_HOST>/supplier/capabilities
```

Example response (200):

```json
{
  "carries_inventory": "yes",
  "offers_custom_orders": "no",
  "minimum_order_amount": 100,
  "accepts_urgent_requests": "yes",
  "offers_credit_accounts": "no"
}
```

9) PUT `/capabilities`
- Purpose: Update supplier capabilities.
- Auth: Required; must be Supplier.
- Request body (JSON): `SupplierCapabilitiesUpdate` fields (optional):
  - `carries_inventory`, `offers_custom_orders`, `minimum_order_amount`, `accepts_urgent_requests`, `offers_credit_accounts`.
  - Boolean-like `yes/no/true/false/1/0` values are accepted for the yes/no fields and normalized by `_normalize_yes_no`.
- Response (200): updated `SupplierCapabilities`.

Example curl:

```bash
curl -X PUT -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{"carries_inventory":"yes","minimum_order_amount":100}' \
  https://<API_HOST>/supplier/capabilities
```

Example success response (200):

```json
{
  "carries_inventory": "yes",
  "offers_custom_orders": "no",
  "minimum_order_amount": 100,
  "accepts_urgent_requests": "no",
  "offers_credit_accounts": "no"
}
```


10) GET `/products`
- Purpose: Retrieve supplier product categories and types.
- Auth: Required; must be Supplier.
- Response (200): `SupplierProducts`:
  - `product_categories` (string), `product_types` (array).

Example curl:

```bash
curl -H "Authorization: Bearer <TOKEN>" https://<API_HOST>/supplier/products
```

Example response (200):

```json
{
  "product_categories": "Flooring",
  "product_types": ["Tile","Hardwood"]
}
```

11) PUT `/products`
- Purpose: Update product categories & types.
- Auth: Required; must be Supplier.
- Request body (JSON): `SupplierProductsUpdate` fields (optional):
  - `product_categories` (string), `product_types` (array of strings).
- Response (200): updated `SupplierProducts`.

Example curl:

```bash
curl -X PUT -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{"product_categories":"Flooring","product_types":["Tile","Hardwood"]}' \
  https://<API_HOST>/supplier/products
```

Example success response (200):

```json
{
  "product_categories": "Flooring",
  "product_types": ["Tile","Hardwood"]
}
```


Notes & Implementation details
- Role check: `_require_supplier()` verifies `current_user.role` and returns 403 if not `Supplier`.
- Supplier lookup: `_get_supplier()` obtains the `models.user.Supplier` record keyed by `current_user.id` and returns 404 if missing.
- Normalization: `_normalize_yes_no()` accepts several truthy/falsey string values and returns standardized `"yes"`/`"no"`, raising 400 on invalid input.
- Password updates (PUT `/account`): the endpoint uses `verify_password()` to check `current_password` and `hash_password()` to set a new hash; these utilities are implemented in `src/app/api/endpoints/auth.py`.

Related files
- Endpoint implementation: `src/app/api/endpoints/supplier.py`
- Schemas: `src/app/schemas/supplier.py` (request/response types)
- Models: `src/app/models/user.py` (Supplier model)

Next steps
- I can generate example request/response JSON using the actual Pydantic schemas from `src/app/schemas/supplier.py`. Want me to add those detailed schema-based examples now?
