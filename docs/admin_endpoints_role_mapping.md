# Admin Endpoints Role-Based Access Control (RBAC) Mapping

## Role Definitions

- **Admin**: Full access to all endpoints (read and write)
- **Ops**: Dashboard, Activity Feed, Users (edit eligibility), Marketplace (Leads/Job Intake/Queue), Operations (all 3)
- **Billing**: Dashboard, Activity Feed, Users (read), Billing (all 4), Support pages (read/assist)

## Access Rules

- **GET endpoints**: Accessible to all roles (Admin, Ops, Billing)
- **POST/PATCH/PUT/DELETE endpoints**: Restricted based on role permissions

---

## Endpoint Access Matrix

| # | Method | Endpoint | Full Name | Admin | Ops | Billing | Notes |
|---|--------|----------|-----------|-------|-----|---------|-------|
| **ANALYTICS & DASHBOARD** |
| 1 | GET | `/admin/dashboard/analytics` | Analytics Dashboard | ✅ | ✅ | ✅ | Dashboard - all roles |
| 2 | GET | `/admin/dashboard/charts/credits-flow` | Credits Flow Chart | ✅ | ✅ | ✅ | Dashboard - all roles |
| 3 | GET | `/admin/dashboard/charts/marketplace-funnel` | Marketplace Funnel Chart | ✅ | ✅ | ✅ | Dashboard - all roles |
| 4 | GET | `/admin/dashboard/tables/categories/search` | Categories Table Search | ✅ | ✅ | ✅ | Dashboard - all roles |
| 5 | GET | `/admin/dashboard/tables/jurisdictions/search` | Jurisdictions Table Search | ✅ | ✅ | ✅ | Dashboard - all roles |
| 6 | GET | `/admin/dashboard/export/categories` | Export Categories | ✅ | ✅ | ✅ | Dashboard - all roles |
| 7 | GET | `/admin/dashboard/export/jurisdictions` | Export Jurisdictions | ✅ | ✅ | ✅ | Dashboard - all roles |
| **CONTRACTORS MANAGEMENT** |
| 8 | GET | `/admin/dashboard/contractors-kpis` | Contractors KPIs | ✅ | ✅ | ✅ | Dashboard - all roles |
| 9 | GET | `/admin/dashboard/contractors-summary` | Contractors Summary | ✅ | ✅ | ✅ | Dashboard - all roles |
| 10 | GET | `/admin/dashboard/contractors/{contractor_id}` | Get Contractor Details | ✅ | ✅ | ✅ | Users (read) - all roles |
| 11 | GET | `/admin/dashboard/contractors/search` | Search Contractors | ✅ | ✅ | ✅ | Users (read) - all roles |
| 12 | GET | `/admin/dashboard/contractors-pending` | Pending Contractors | ✅ | ✅ | ✅ | Users (read) - all roles |
| 13 | GET | `/admin/dashboard/contractors/onboarding/{user_id}` | Contractor Onboarding | ✅ | ✅ | ✅ | Users (read) - all roles |
| 14 | PATCH | `/admin/dashboard/contractors/{contractor_id}/active` | Toggle Contractor Active Status | ✅ | ✅ | ❌ | Users (edit eligibility) - Ops + Admin |
| 15 | PATCH | `/admin/dashboard/contractors/{contractor_id}/approval` | Approve/Reject Contractor | ✅ | ✅ | ❌ | Users (edit eligibility) - Ops + Admin |
| **SUPPLIERS MANAGEMENT** |
| 16 | GET | `/admin/dashboard/suppliers-kpis` | Suppliers KPIs | ✅ | ✅ | ✅ | Dashboard - all roles |
| 17 | GET | `/admin/dashboard/suppliers-summary` | Suppliers Summary | ✅ | ✅ | ✅ | Dashboard - all roles |
| 18 | GET | `/admin/dashboard/suppliers/{supplier_id}` | Get Supplier Details | ✅ | ✅ | ✅ | Users (read) - all roles |
| 19 | GET | `/admin/dashboard/suppliers/search` | Search Suppliers | ✅ | ✅ | ✅ | Users (read) - all roles |
| 20 | GET | `/admin/dashboard/suppliers-pending` | Pending Suppliers | ✅ | ✅ | ✅ | Users (read) - all roles |
| 21 | GET | `/admin/dashboard/suppliers/onboarding/{user_id}` | Supplier Onboarding | ✅ | ✅ | ✅ | Users (read) - all roles |
| 22 | PATCH | `/admin/dashboard/suppliers/{supplier_id}/active` | Toggle Supplier Active Status | ✅ | ✅ | ❌ | Users (edit eligibility) - Ops + Admin |
| 23 | PATCH | `/admin/dashboard/suppliers/{supplier_id}/approval` | Approve/Reject Supplier | ✅ | ✅ | ❌ | Users (edit eligibility) - Ops + Admin |
| **SETTINGS** |
| 24 | GET | `/admin/dashboard/settings/auto-post-jobs` | Get Auto-Post Jobs Setting | ✅ | ✅ | ✅ | Dashboard - all roles |
| 25 | PATCH | `/admin/dashboard/settings/auto-post-jobs` | Update Auto-Post Jobs Setting | ✅ | ✅ | ❌ | Operations - Ops + Admin |
| **INGESTED JOBS (SYSTEM)** |
| 26 | GET | `/admin/dashboard/ingested-jobs/system` | System Ingested Jobs List | ✅ | ✅ | ✅ | Marketplace (Job Intake) - all roles |
| 27 | GET | `/admin/dashboard/ingested-jobs/system/search` | Search System Ingested Jobs | ✅ | ✅ | ✅ | Marketplace (Job Intake) - all roles |
| 28 | GET | `/admin/dashboard/ingested-jobs/posted` | Posted Jobs List | ✅ | ✅ | ✅ | Marketplace (Queue) - all roles |
| 29 | GET | `/admin/dashboard/ingested-jobs/posted/search` | Search Posted Jobs | ✅ | ✅ | ✅ | Marketplace (Queue) - all roles |
| 30 | GET | `/admin/dashboard/ingested-jobs/posted/{job_id}` | Get Posted Job Details | ✅ | ✅ | ✅ | Marketplace (Queue) - all roles |
| 31 | PATCH | `/admin/dashboard/ingested-jobs/{job_id}` | Update Ingested Job | ✅ | ✅ | ❌ | Marketplace (Job Intake/Queue) - Ops + Admin |
| 32 | DELETE | `/admin/dashboard/ingested-jobs/{job_id}` | Delete Ingested Job | ✅ | ✅ | ❌ | Marketplace (Job Intake/Queue) - Ops + Admin |
| **CONTRACTOR UPLOADED JOBS** |
| 33 | GET | `/admin/dashboard/contractor-uploaded-jobs` | Contractor Uploaded Jobs List | ✅ | ✅ | ✅ | Marketplace (Leads) - all roles |
| 34 | GET | `/admin/dashboard/contractor-uploaded-jobs/search` | Search Contractor Uploaded Jobs | ✅ | ✅ | ✅ | Marketplace (Leads) - all roles |
| 35 | GET | `/admin/dashboard/contractor-uploaded-jobs/{job_id}` | Get Contractor Uploaded Job Details | ✅ | ✅ | ✅ | Marketplace (Leads) - all roles |
| 36 | PATCH | `/ingested-jobs/{job_id}/decline` | Decline Ingested Job | ✅ | ✅ | ❌ | Marketplace (Queue) - Ops + Admin |
| **JOBS (USER-FACING)** |
| 37 | GET | `/jobs/job/{job_id}` | Get Job Details | ✅ | ✅ | ✅ | Support pages (read) - all roles |
| 38 | GET | `/jobs/my-uploaded-jobs` | Get User's Uploaded Jobs | ✅ | ✅ | ✅ | Support pages (read) - all roles |
| 39 | PATCH | `/jobs/job/{job_id}/repost` | Repost Job | ✅ | ✅ | ✅ | Support pages (assist) - all roles |
| 40 | POST | `/jobs/job/{job_id}/documents` | Upload Job Document | ✅ | ✅ | ✅ | Support pages (assist) - all roles |
| 41 | POST | `/jobs/upload-temp-documents` | Upload Temp Documents | ✅ | ✅ | ✅ | Support pages (assist) - all roles |
| 42 | DELETE | `/jobs/job/{job_id}/documents/{document_id}` | Delete Job Document | ✅ | ✅ | ✅ | Support pages (assist) - all roles |
| 43 | GET | `/jobs/temp-documents/preview` | Preview Temp Documents | ✅ | ✅ | ✅ | Support pages (read) - all roles |
| 44 | DELETE | `/jobs/temp-documents/{temp_upload_id}/{document_id}` | Delete Temp Document | ✅ | ✅ | ✅ | Support pages (assist) - all roles |
| 45 | GET | `/jobs/download-upload-template` | Download Upload Template | ✅ | ✅ | ✅ | Support pages (read) - all roles |
| 46 | POST | `/jobs/upload-leads` | Upload Leads | ✅ | ✅ | ❌ | Marketplace (Leads) - Ops + Admin |
| **SUBSCRIPTIONS & BILLING** |
| 47 | GET | `/admin/subscriptions/dashboard` | Subscriptions Dashboard | ✅ | ✅ | ✅ | Billing - all roles |
| 48 | GET | `/admin/subscriptions/dashboard/search` | Search Subscriptions Dashboard | ✅ | ✅ | ✅ | Billing - all roles |
| 49 | GET | `/admin/subscriptions/plans` | Get Subscription Plans | ✅ | ✅ | ✅ | Billing - all roles |
| 50 | PUT | `/admin/subscriptions/update-all-tiers-pricing` | Update All Tiers Pricing | ✅ | ❌ | ✅ | Billing - Billing + Admin |
| 51 | GET | `/admin/subscriptions/credits-ledger` | Credits Ledger | ✅ | ✅ | ✅ | Billing - all roles |
| 52 | PATCH | `/admin/subscriptions/credits-ledger/{user_id}` | Update Credits Ledger | ✅ | ❌ | ✅ | Billing - Billing + Admin |
| 53 | GET | `/admin/subscriptions/subscriptions-list` | Subscriptions List | ✅ | ✅ | ✅ | Billing - all roles |
| 54 | GET | `/admin/subscriptions/payments` | Payments List | ✅ | ✅ | ✅ | Billing - all roles |
| **PENDING JURISDICTIONS** |
| 55 | GET | `/admin/dashboard/pending-jurisdictions` | List Pending Jurisdictions | ✅ | ✅ | ✅ | Users (read) - all roles |
| 56 | PATCH | `/admin/dashboard/pending-jurisdictions/{pending_id}/approve` | Approve Pending Jurisdiction | ✅ | ✅ | ❌ | Users (edit eligibility) - Ops + Admin |
| 57 | PATCH | `/admin/dashboard/pending-jurisdictions/{pending_id}/reject` | Reject Pending Jurisdiction | ✅ | ✅ | ❌ | Users (edit eligibility) - Ops + Admin |
| **AUTHENTICATION** |
| 58 | POST | `/auth/login` | User Login | ✅ | ✅ | ✅ | Public auth - all roles |
| 59 | POST | `/auth/refresh` | Refresh Token | ✅ | ✅ | ✅ | Public auth - all roles |
| 60 | POST | `/auth/logout` | User Logout | ✅ | ✅ | ✅ | Public auth - all roles |
| 61 | POST | `/admin/login` | Admin Login | ✅ | ✅ | ✅ | Public auth - all roles |

---

## Summary by Role

### Admin
- **Access**: All endpoints (GET, POST, PATCH, PUT, DELETE)
- **Total**: 61 endpoints

### Ops
- **Access**: 
  - All GET endpoints (read-only access)
  - POST/PATCH/PUT/DELETE for:
    - Users (edit eligibility): Contractor/Supplier approval, active status, pending jurisdictions
    - Marketplace (Leads/Job Intake/Queue): Job updates, deletions, decline, upload leads
    - Operations: Auto-post jobs settings
- **Total**: 61 endpoints (all GET + 15 write endpoints)

### Billing
- **Access**:
  - All GET endpoints (read-only access)
  - POST/PATCH/PUT/DELETE for:
    - Billing: Update pricing, update credits ledger
    - Support pages (assist): Job repost, document upload/delete
- **Total**: 61 endpoints (all GET + 6 write endpoints)

---

## Implementation Notes

1. **Role Field**: AdminUser model should have a `role` column with values: `"admin"`, `"ops"`, `"billing"`

2. **Dependency Functions Needed**:
   - `require_admin_role()` - Admin only
   - `require_ops_or_admin()` - Ops or Admin
   - `require_billing_or_admin()` - Billing or Admin
   - `require_any_admin_role()` - All admin roles (for GET endpoints)

3. **GET Endpoints**: All GET endpoints should use `require_any_admin_role()` to allow all three roles

4. **Write Endpoints**: Use role-specific dependencies based on the matrix above

5. **Auth Endpoints**: `/auth/*` and `/admin/login` are public (no role check needed)

