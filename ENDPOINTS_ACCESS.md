# API Endpoints — Access Reference

**Access Level Key:**
| Label | Who can call it |
|-------|----------------|
| `Public` | No authentication required |
| `All` | Any authenticated user — Main, Editor, Viewer |
| `Main, Editor` | Main account + Editor sub-accounts only (Viewers blocked) |
| `Main` | Main account only (Editors and Viewers blocked) |
| `Admin` | Admin JWT only |

---

## Authentication — `/auth`

| Method | Endpoint                    | Access |
| ------ | --------------------------- | ------ |
| POST   | `/auth/signup`              | Public |
| POST   | `/auth/verify/{email}`      | Public |
| POST   | `/auth/resend-otp`          | Public |
| POST   | `/auth/login`               | Public |
| POST   | `/auth/token`               | Public |
| POST   | `/auth/forgot-password`     | Public |
| POST   | `/auth/reset-password`      | Public |
| POST   | `/auth/refresh`             | Public |
| POST   | `/auth/set-role`            | All    |
| GET    | `/auth/get-role`            | All    |
| GET    | `/auth/me`                  | All    |
| GET    | `/auth/registration-status` | All    |
| GET    | `/auth/status`              | All    |
| POST   | `/auth/logout`              | All    |
| DELETE | `/auth/delete-account`      | All    |

---

## Two-Factor Authentication — `/auth/2fa`

| Method | Endpoint                      | Access |
| ------ | ----------------------------- | ------ |
| GET    | `/auth/2fa/status`            | All    |
| POST   | `/auth/2fa/setup`             | All    |
| POST   | `/auth/2fa/verify-and-enable` | All    |
| POST   | `/auth/2fa/verify-login`      | All    |
| POST   | `/auth/2fa/disable`           | All    |
| POST   | `/auth/2fa/request-recovery`  | All    |
| POST   | `/auth/2fa/verify-recovery`   | Public |

---

## Contractor Profile — `/contractor`

| Method | Endpoint                                                   | Access       |
| ------ | ---------------------------------------------------------- | ------------ |
| GET    | `/contractor/profile`                                      | All          |
| GET    | `/contractor/account`                                      | All          |
| PATCH  | `/contractor/account`                                      | **Main**     |
| GET    | `/contractor/business-details`                             | All          |
| PATCH  | `/contractor/business-details`                             | Main, Editor |
| GET    | `/contractor/license-info`                                 | All          |
| PATCH  | `/contractor/license-info`                                 | **Main**     |
| GET    | `/contractor/trade-info`                                   | All          |
| PATCH  | `/contractor/trade-info`                                   | Main, Editor |
| GET    | `/contractor/location-info`                                | All          |
| PATCH  | `/contractor/location-info`                                | Main, Editor |
| GET    | `/contractor/preview-documents`                            | All          |
| DELETE | `/contractor/delete-document/{document_type}/{file_index}` | Main, Editor |
| POST   | `/contractor/step-1`                                       | Main, Editor |
| POST   | `/contractor/step-2`                                       | Main, Editor |
| POST   | `/contractor/step-3`                                       | Main, Editor |
| POST   | `/contractor/step-4`                                       | Main, Editor |

---

## Supplier Profile — `/supplier`

| Method | Endpoint                                                 | Access       |
| ------ | -------------------------------------------------------- | ------------ |
| GET    | `/supplier/profile`                                      | All          |
| GET    | `/supplier/account`                                      | All          |
| PATCH  | `/supplier/account`                                      | **Main**     |
| GET    | `/supplier/business-details`                             | All          |
| PATCH  | `/supplier/business-details`                             | Main, Editor |
| GET    | `/supplier/license-info`                                 | All          |
| PATCH  | `/supplier/license-info`                                 | **Main**     |
| GET    | `/supplier/location-info`                                | All          |
| PATCH  | `/supplier/location-info`                                | Main, Editor |
| GET    | `/supplier/user-type`                                    | All          |
| PATCH  | `/supplier/user-type`                                    | Main, Editor |
| GET    | `/supplier/preview-documents`                            | All          |
| DELETE | `/supplier/delete-document/{document_type}/{file_index}` | Main, Editor |
| POST   | `/supplier/step-1`                                       | Main, Editor |
| POST   | `/supplier/step-2`                                       | Main, Editor |
| POST   | `/supplier/step-3`                                       | Main, Editor |
| POST   | `/supplier/step-4`                                       | Main, Editor |

---

## Jobs — `/jobs`

| Method | Endpoint                                              | Access       |
| ------ | ----------------------------------------------------- | ------------ |
| GET    | `/jobs/feed`                                          | All          |
| GET    | `/jobs/my-job-feed`                                   | All          |
| GET    | `/jobs/my-saved-job-feed`                             | All          |
| GET    | `/jobs/all`                                           | All          |
| GET    | `/jobs/all-my-jobs`                                   | All          |
| GET    | `/jobs/all-my-jobs-desktop`                           | All          |
| GET    | `/jobs/all-my-jobs-desktop-search`                    | All          |
| GET    | `/jobs/all-my-saved-jobs`                             | All          |
| GET    | `/jobs/search`                                        | All          |
| GET    | `/jobs/search-my-jobs`                                | All          |
| GET    | `/jobs/search-saved-jobs`                             | All          |
| GET    | `/jobs/job/{job_id}`                                  | All          |
| GET    | `/jobs/view-details/{job_id}`                         | All          |
| GET    | `/jobs/my-unlocked-leads`                             | All          |
| GET    | `/jobs/export-unlocked-leads`                         | All          |
| GET    | `/jobs/matched-jobs-contractor`                       | All          |
| GET    | `/jobs/matched-jobs-supplier`                         | All          |
| GET    | `/jobs/my-draft-jobs`                                 | All          |
| GET    | `/jobs/draft/{draft_id}`                              | All          |
| GET    | `/jobs/temp-documents/preview`                        | All          |
| POST   | `/jobs/upload-contractor-job`                         | All          |
| POST   | `/jobs/save-draft`                                    | All          |
| POST   | `/jobs/publish-draft/{draft_id}`                      | All          |
| POST   | `/jobs/job/{job_id}/documents`                        | All          |
| POST   | `/jobs/my-feed-not-interested/{job_id}`               | All          |
| POST   | `/jobs/upload-temp-documents`                         | All          |
| POST   | `/jobs/unlock/{job_id}`                               | All          |
| PATCH  | `/jobs/draft/{draft_id}`                              | Main, Editor |
| PATCH  | `/jobs/job/{job_id}/repost`                           | All          |
| PUT    | `/jobs/update-notes/{job_id}`                         | All          |
| DELETE | `/jobs/draft/{draft_id}`                              | All          |
| DELETE | `/jobs/job/{job_id}`                                  | All          |
| DELETE | `/jobs/job/{job_id}/documents/{document_id}`          | All          |
| DELETE | `/jobs/temp-documents/{temp_upload_id}/{document_id}` | All          |
| POST   | `/jobs/upload-leads`                                  | **Admin**    |
| GET    | `/jobs/download-upload-template`                      | **Admin**    |

---

## Dashboard — `/dashboard`

| Method | Endpoint                         | Access       |
| ------ | -------------------------------- | ------------ |
| GET    | `/dashboard/`                    | All          |
| GET    | `/dashboard/jobs-stats`          | All          |
| POST   | `/dashboard/save-job/{job_id}`   | Main, Editor |
| DELETE | `/dashboard/unsave-job/{job_id}` | Main, Editor |
| POST   | `/dashboard/mark-not-interested` | Main, Editor |
| POST   | `/dashboard/unlock-job`          | Main, Editor |

---

## Saved Jobs — `/saved-jobs`

| Method | Endpoint       | Access |
| ------ | -------------- | ------ |
| GET    | `/saved-jobs/` | All    |

---

## Profile & Team — `/profile`

| Method | Endpoint                            | Access |
| ------ | ----------------------------------- | ------ |
| GET    | `/profile/info`                     | All    |
| GET    | `/profile/contact-information`      | All    |
| GET    | `/profile/picture`                  | All    |
| POST   | `/profile/picture`                  | All    |
| DELETE | `/profile/picture`                  | All    |
| GET    | `/profile/team-members`             | All    |
| DELETE | `/profile/team-members/{member_id}` | All    |
| PATCH  | `/profile/team-members/{member_id}` | All    |

---

## Subscription — `/subscription`

| Method | Endpoint                                         | Access                  |
| ------ | ------------------------------------------------ | ----------------------- |
| GET    | `/subscription/plans`                            | All                     |
| GET    | `/subscription/my-subscription`                  | All                     |
| GET    | `/subscription/wallet`                           | All                     |
| GET    | `/subscription/my-add-ons`                       | All                     |
| GET    | `/subscription/payment-history`                  | All                     |
| GET    | `/subscription/payment-receipt/{invoice_number}` | All                     |
| POST   | `/subscription/redeem-add-on`                    | All                     |
| POST   | `/subscription/update-payment-method`            | Main, Editor            |
| POST   | `/subscription/cancel-subscription`              | **Main**                |
| POST   | `/subscription/toggle-auto-renew`                | **Main**                |
| POST   | `/subscription/reactivate-subscription`          | **Main**                |
| POST   | `/subscription/webhook`                          | Public (Stripe webhook) |
| PUT    | `/subscription/admin/update-all-tiers-pricing`   | **Admin**               |

---

## Push Notifications — `/push`

| Method | Endpoint                 | Access |
| ------ | ------------------------ | ------ |
| GET    | `/push/vapid-public-key` | Public |
| POST   | `/push/subscribe`        | All    |
| POST   | `/push/test`             | All    |
| DELETE | `/push/unsubscribe`      | All    |

---

## AI Job Matching — `/ai-matching`

| Method | Endpoint                                   | Access |
| ------ | ------------------------------------------ | ------ |
| POST   | `/ai-matching/suggest-contractors`         | All    |
| POST   | `/ai-matching/suggest-suppliers`           | All    |
| POST   | `/ai-matching/suggest-related-contractors` | All    |
| POST   | `/ai-matching/suggest-related-suppliers`   | All    |

---

## Email Generation — `/groq`

| Method | Endpoint              | Access |
| ------ | --------------------- | ------ |
| POST   | `/groq/generate-send` | All    |

---

## Admin — Subscriptions Dashboard `/admin/subscriptions`

| Method | Endpoint                                        | Access   |
| ------ | ----------------------------------------------- | -------- |
| GET    | `/admin/subscriptions/dashboard`                | Public\* |
| GET    | `/admin/subscriptions/dashboard/search`         | Public\* |
| GET    | `/admin/subscriptions/plans`                    | Public\* |
| GET    | `/admin/subscriptions/credits-ledger`           | Public\* |
| PATCH  | `/admin/subscriptions/credits-ledger/{user_id}` | Public\* |
| GET    | `/admin/subscriptions/subscriptions-list`       | Public\* |
| GET    | `/admin/subscriptions/payments`                 | Public\* |

> \* These routes currently only require `get_db` — no auth guard applied in code.

---

## Summary by Access Level

| Access                       | Count |
| ---------------------------- | ----- |
| Public                       | 12    |
| All (Main + Editor + Viewer) | 63    |
| Main + Editor                | 17    |
| Main only                    | 7     |
| Admin                        | 3     |
