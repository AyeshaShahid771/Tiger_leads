# Automatic Job Cleanup After 7 Days

## Overview

Jobs with `job_review_status = 'posted'` are **automatically deleted** 7 days after being posted. The cleanup service runs in the background automatically when your server starts - **no manual intervention needed**.

## How It Works

1. **Tracking**: When a job's `job_review_status` is set to `'posted'`, the `review_posted_at` timestamp is automatically recorded
2. **Background Service**: A cleanup service runs every hour checking for jobs to delete
3. **Automatic Deletion**: Jobs 7+ days old are automatically deleted

## ✨ New: Fully Automated Cleanup

The cleanup service now runs **automatically in the background**:

- ✅ Starts when your server starts
- ✅ Runs every hour checking for old jobs
- ✅ Deletes jobs 7+ days after posting
- ✅ No manual API calls needed
- ✅ No cron jobs or task scheduler needed

### When Are Jobs Tracked?

| Action | File | Status | Timestamp Set? |
|--------|------|--------|----------------|
| **Contractor uploads job** | `jobs.py` | `pending` | ❌ No (awaits admin approval) |
| **Admin bulk upload** | `jobs.py` | `posted` | ✅ Yes (immediate) |
| **Admin approves job** | `admin_dashboard.py` | `pending`→`posted` | ✅ Yes (on approval) |

📖 **For detailed flow, see [JOB_STATUS_TRACKING.md](JOB_STATUS_TRACKING.md)**

## Database Changes

### New Column Added

- **Table**: `jobs`
- **Column**: `review_posted_at` (TIMESTAMP, nullable)
- **Purpose**: Tracks when a job was marked as 'posted'

## Setup Instructions

### 1. Run Migration

First, add the `review_posted_at` column to your database:

```bash
# Activate your virtual environment
Tiger_leads\Scripts\activate.bat

# Run the migration
python add_review_posted_at_column.py
```

This will:
- Add the `review_posted_at` column to the `jobs` table
- Set `review_posted_at = created_at` for existing posted jobs

### 2. Restart Your Server

The cleanup service starts automatically when you run:

```bash
uvicorn src.app.main:app --reload
```

**You should see in the logs:**
```
INFO:     Starting background services...
INFO:     Job cleanup service started (checking every 1 hour(s))
INFO:     ✓ Job cleanup service started successfully
```

**That's it!** The service is now running and will automatically delete old jobs every hour.

---

## Monitoring

### View Cleanup Logs

Every hour, you'll see logs like:

```
INFO:     [Job Cleanup] Starting cleanup check (cutoff: 2025-12-29T10:00:00)
INFO:     [Job Cleanup] ✓ Successfully deleted 45 jobs
INFO:     [Job Cleanup] Deleted job IDs: [123, 124, 125, ...]
```

Or if no jobs need deletion:

```
INFO:     [Job Cleanup] Starting cleanup check (cutoff: 2025-12-29T10:00:00)
INFO:     [Job Cleanup] No jobs to delete
```

---

## Optional: Manual Control

### Preview Jobs to be Deleted (API)

```http
GET /admin/dashboard/jobs/cleanup/preview
Authorization: Bearer <admin_token>
```

**Response:**
```json
{
  "total_count": 45,
  "cutoff_date": "2025-12-29T00:00:00",
  "preview_jobs": [
    {
      "id": 123,
      "permit_type": "Building Permit",
      "state": "CA",
      "review_posted_at": "2025-12-20T10:30:00",
      "days_since_posted": 16
    }
  ],
  "message": "Found 45 jobs that are 7+ days old and will be deleted."
}
```

#### Execute Cleanup

```http
DELETE /admin/dashboard/jobs/cleanup
Authorization: Bearer <admin_token>
```

**Response:**
```json
{
  "success": true,
  "deleted_count": 45,
  "message": "Successfully deleted 45 jobs that were posted 7 or more days ago.",
  "deleted_job_ids": [123, 124, 125, ...],
  "cutoff_date": "2025-12-29T00:00:00"
}
```

### Manual Trigger Cleanup (API)

If you want to trigger cleanup immediately instead of waiting for the hourly check:

```http
DELETE /admin/dashboard/jobs/cleanup
Authorization: Bearer <admin_token>
```

**Response:**
```json
{
  "success": true,
  "deleted_count": 45,
  "message": "Successfully deleted 45 jobs that were posted 7 or more days ago.",
  "deleted_job_ids": [123, 124, 125, ...],
  "cutoff_date": "2025-12-29T00:00:00"
}
```

---

## Configuration

### Change Check Frequency

**Default:** Every 1 hour

**To change:** Edit `src/app/services/job_cleanup_service.py` (bottom of file):

```python
# Change from 1 hour to 6 hours
job_cleanup_service = JobCleanupService(check_interval_hours=6)
```

### Change Deletion Period

**Default:** 7 days

**To change:** Edit `src/app/services/job_cleanup_service.py` line ~77:

```python
# Change from 7 days to 14 days
cutoff_date = datetime.utcnow() - timedelta(days=14)
```

---

## What Gets Deleted vs. What Doesn't

### ✅ Gets Deleted Automatically

Jobs where ALL conditions are met:
- `job_review_status = 'posted'`
- `review_posted_at` is NOT NULL  
- `review_posted_at` is 7+ days old

### ❌ Never Gets Deleted

- Jobs with status `'pending'` (awaiting admin review)
- Jobs with status `'declined'` (rejected by admin)
- Jobs where `review_posted_at` is NULL
- Jobs posted less than 7 days ago

---

## Example Timeline

**Contractor Upload → Admin Approval → Auto-Delete:**

```
Day 0, 10:00 AM - Contractor uploads job
├─ Status: 'pending'
├─ Timestamp: NULL
└─ Not eligible for deletion

Day 2, 2:00 PM - Admin approves job
├─ Status: 'posted'
├─ Timestamp: 2026-01-02 14:00:00
└─ 7-day countdown starts

Day 3, 3:00 PM - Background service checks (hourly)
└─ Not old enough yet

Day 9, 3:00 PM - Background service checks
├─ Age: 7 days, 1 hour
├─ Condition met: >= 7 days
└─ ✓ Job DELETED automatically
```

**Admin Bulk Upload → Auto-Delete:**

```
Day 0, 9:00 AM - Admin bulk uploads 100 jobs
├─ All created with status: 'posted'
├─ All have timestamp: 2026-01-05 09:00:00
└─ 7-day countdown starts immediately

Day 7, 10:00 AM - Background service checks
├─ All 100 jobs are 7+ days old
└─ ✓ All 100 jobs DELETED automatically
```

---

## Old Method (No Longer Needed)

### ~~Option 2: Automated Cleanup (Recommended)~~

**Note:** The scheduled script method is **NO LONGER NEEDED**. The background service handles everything automatically.

~~If you prefer using Task Scheduler or cron instead of the background service, you can still use `cleanup_jobs_scheduler.py`~~ - but it's not necessary anymore.

---

## Troubleshooting

### Background Service Not Starting

**Check server logs for:**
```
ERROR: Failed to start job cleanup service: ...
```

**Solution:**
1. Verify database connection is working
2. Check for import errors in logs
3. Ensure `src/app/services/` directory exists

### Jobs Not Being Deleted

1. **Verify column exists:**
   ```sql
   SELECT column_name FROM information_schema.columns 
   WHERE table_name='jobs' AND column_name='review_posted_at';
   ```

2. **Check timestamps:**
   ```sql
   SELECT id, job_review_status, review_posted_at,
          EXTRACT(DAY FROM (NOW() - review_posted_at)) as days_old
   FROM jobs 
   WHERE job_review_status='posted' 
   ORDER BY review_posted_at;
   ```

3. **Wait for next hourly check** - Service runs every hour

4. **Test manually** - Use the preview endpoint to see eligible jobs

### Service Runs But Doesn't Delete

**Check if jobs meet ALL criteria:**
- Status must be exactly `'posted'`
- `review_posted_at` must NOT be NULL
- Must be 7+ days old

---

## Safety Features

1. **Hourly checks**: Service runs every hour, not continuously
2. **7-day buffer**: Full week before deletion
3. **Status validation**: Only deletes explicitly 'posted' jobs
4. **Transaction rollback**: Auto-rollback on errors
5. **Detailed logging**: All operations logged with timestamps
6. **Graceful shutdown**: Stops cleanly when server stops

---

## Files Created/Modified

### New Files
- `src/app/services/job_cleanup_service.py` - Background cleanup service
- `src/app/services/__init__.py` - Services package init
- `add_review_posted_at_column.py` - Database migration script
- `JOB_CLEANUP_GUIDE.md` - This guide
- `JOB_STATUS_TRACKING.md` - Technical documentation

### Modified Files  
- `src/app/models/user.py` - Added `review_posted_at` column
- `src/app/main.py` - Added startup/shutdown events for service
- `src/app/api/endpoints/admin_dashboard.py` - Set timestamp when marking posted
- `src/app/api/endpoints/jobs.py` - Set timestamp on bulk upload

## API Reference

### Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/admin/dashboard/jobs/cleanup/preview` | Preview jobs to be deleted | Admin Token |
| DELETE | `/admin/dashboard/jobs/cleanup` | Execute cleanup (delete old jobs) | Admin Token |
| PATCH | `/admin/dashboard/ingested-jobs/{job_id}/post` | Mark job as posted (sets timestamp) | Admin/Editor |

## Files Modified/Created

### Modified
- `src/app/models/user.py` - Added `review_posted_at` column to Job model
- `src/app/api/endpoints/admin_dashboard.py` - Added cleanup endpoints and timestamp setting
- `src/app/api/endpoints/jobs.py` - Set timestamp on bulk upload

### Created
- `add_review_posted_at_column.py` - Migration script
- `cleanup_jobs_scheduler.py` - Scheduled cleanup script
- `JOB_CLEANUP_GUIDE.md` - This documentation

## Questions?

For issues or questions, check the logs or contact the development team.
