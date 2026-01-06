# Job Review Status Tracking - Technical Documentation

## How `review_posted_at` Timestamp is Tracked

### Overview
The `review_posted_at` column tracks when a job's `job_review_status` was set to `'posted'`. This timestamp is used for automatic deletion 7 days later.

## All Places Where Jobs Are Created or Status Changes

### 1. **Contractor Job Upload** 
**File:** `src/app/api/endpoints/jobs.py`  
**Endpoint:** `POST /api/jobs/upload-contractor-job`  
**Line:** ~269

```python
job = models.user.Job(
    # ... other fields ...
    job_review_status="pending",  # ← Status is 'pending', NOT 'posted'
    # review_posted_at is NOT set here (remains NULL)
)
```

**Status:** `pending`  
**Timestamp Set?** ❌ No - Jobs uploaded by contractors start as "pending" and need admin review  
**Why?** Contractor-uploaded jobs require admin approval before being posted

---

### 2. **Admin Bulk Job Upload**
**File:** `src/app/api/endpoints/jobs.py`  
**Endpoint:** `POST /api/jobs/bulk-upload`  
**Line:** ~603

```python
job = models.user.Job(
    # ... other fields ...
    job_review_status="posted",              # ← Status is 'posted'
    review_posted_at=datetime.utcnow(),      # ← Timestamp SET HERE
)
```

**Status:** `posted`  
**Timestamp Set?** ✅ Yes - `review_posted_at = datetime.utcnow()`  
**Why?** Admin bulk uploads are automatically posted (admin-uploaded jobs are pre-approved)

---

### 3. **Admin Marks Job as Posted**
**File:** `src/app/api/endpoints/admin_dashboard.py`  
**Endpoint:** `PATCH /admin/dashboard/ingested-jobs/{job_id}/post`  
**Line:** ~746

```python
def post_ingested_job(job_id: int, db: Session = Depends(get_db)):
    j = db.query(models.user.Job).filter(models.user.Job.id == job_id).first()
    
    j.job_review_status = "posted"           # ← Status changed to 'posted'
    j.review_posted_at = datetime.utcnow()   # ← Timestamp SET HERE
    db.commit()
```

**Status:** `pending` → `posted`  
**Timestamp Set?** ✅ Yes - `review_posted_at = datetime.utcnow()`  
**Why?** This is when admin approves a contractor-uploaded job

---

## Automatic Deletion Flow

### How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│  Job Creation/Status Change                                     │
│  ┌──────────────────┐         ┌─────────────────────┐          │
│  │ Contractor Upload│         │ Admin Bulk Upload   │          │
│  │ status='pending' │         │ status='posted'     │          │
│  │ timestamp=NULL   │         │ timestamp=NOW       │          │
│  └────────┬─────────┘         └──────────┬──────────┘          │
│           │                              │                      │
│           │                              │                      │
│           ▼                              ▼                      │
│  ┌──────────────────────────────────────────────────┐          │
│  │ Admin Reviews & Posts Job                        │          │
│  │ (PATCH /admin/dashboard/ingested-jobs/{id}/post) │          │
│  │                                                   │          │
│  │ status='pending' → 'posted'                      │          │
│  │ timestamp=NOW                                    │          │
│  └──────────────────────┬───────────────────────────┘          │
│                         │                                       │
└─────────────────────────┼───────────────────────────────────────┘
                          │
                          ▼
         ┌────────────────────────────────────────┐
         │  Job with status='posted'               │
         │  review_posted_at = timestamp           │
         │                                         │
         │  Wait 7 days...                         │
         └────────────┬───────────────────────────┘
                      │
                      ▼
         ┌────────────────────────────────────────┐
         │  Background Service (runs hourly)       │
         │                                         │
         │  Checks:                                │
         │  - job_review_status == 'posted'        │
         │  - review_posted_at IS NOT NULL         │
         │  - review_posted_at <= 7 days ago       │
         │                                         │
         │  ✓ Deletes matching jobs automatically  │
         └─────────────────────────────────────────┘
```

---

## Automatic Deletion Service

### Background Service Configuration

**File:** `src/app/services/job_cleanup_service.py`

- **Runs:** Automatically in the background
- **Frequency:** Every 1 hour (configurable)
- **Starts:** When FastAPI app starts
- **Stops:** When FastAPI app shuts down

### How to Change Check Frequency

Edit `src/app/services/job_cleanup_service.py`:

```python
# Change from 1 hour to a different interval
job_cleanup_service = JobCleanupService(check_interval_hours=6)  # Check every 6 hours
```

### What Gets Deleted

Jobs are ONLY deleted when ALL conditions are met:

1. `job_review_status = 'posted'`
2. `review_posted_at IS NOT NULL`
3. `review_posted_at <= (current_time - 7 days)`

### What NEVER Gets Deleted

- Jobs with `job_review_status = 'pending'` (contractor uploads awaiting review)
- Jobs with `job_review_status = 'declined'` (rejected jobs)
- Jobs where `review_posted_at IS NULL`
- Jobs posted less than 7 days ago

---

## Complete Timeline Example

### Example: Contractor Uploads a Job

```
Day 0, 10:00 AM
├─ Contractor uploads job via POST /api/jobs/upload-contractor-job
├─ job_review_status = 'pending'
├─ review_posted_at = NULL
└─ ✗ Not eligible for deletion (status is 'pending')

Day 2, 2:00 PM
├─ Admin approves via PATCH /admin/dashboard/ingested-jobs/123/post
├─ job_review_status = 'posted'
├─ review_posted_at = '2026-01-02 14:00:00'
└─ ✓ 7-day countdown starts NOW

Day 9, 3:00 PM (7 days + 1 hour later)
├─ Background service runs hourly check
├─ Finds job where review_posted_at = '2026-01-02 14:00:00'
├─ Calculates: (2026-01-09 15:00:00) - (2026-01-02 14:00:00) = 7 days, 1 hour
├─ Condition met: 7 days, 1 hour >= 7 days
└─ ✓ Job DELETED automatically
```

### Example: Admin Bulk Upload

```
Day 0, 9:00 AM
├─ Admin uploads 100 jobs via POST /api/jobs/bulk-upload
├─ All jobs created with:
│  ├─ job_review_status = 'posted'
│  └─ review_posted_at = '2026-01-05 09:00:00'
└─ ✓ 7-day countdown starts immediately

Day 7, 10:00 AM (exactly 7 days + 1 hour later)
├─ Background service runs
├─ Finds all 100 jobs where review_posted_at = '2026-01-05 09:00:00'
├─ All meet deletion criteria
└─ ✓ All 100 jobs DELETED automatically
```

---

## Monitoring & Logs

### Startup Logs

When you start the server, you'll see:

```
INFO:     Starting background services...
INFO:     Job cleanup service started (checking every 1 hour(s))
INFO:     ✓ Job cleanup service started successfully
```

### Cleanup Logs (Every Hour)

```
INFO:     [Job Cleanup] Starting cleanup check (cutoff: 2025-12-29T10:00:00)
INFO:     [Job Cleanup] ✓ Successfully deleted 45 jobs
INFO:     [Job Cleanup] Deleted job IDs: [123, 124, 125, 126, ...]
```

### No Jobs to Delete

```
INFO:     [Job Cleanup] Starting cleanup check (cutoff: 2025-12-29T10:00:00)
INFO:     [Job Cleanup] No jobs to delete
```

### Shutdown Logs

```
INFO:     Stopping background services...
INFO:     ✓ Job cleanup service stopped successfully
```

---

## Configuration

### Change Deletion Period (from 7 days to something else)

**Option 1:** Edit `src/app/services/job_cleanup_service.py` line ~77:

```python
cutoff_date = datetime.utcnow() - timedelta(days=14)  # Change to 14 days
```

**Option 2:** Make it configurable via environment variable:

```python
import os

DELETION_DAYS = int(os.getenv("JOB_DELETION_DAYS", "7"))
cutoff_date = datetime.utcnow() - timedelta(days=DELETION_DAYS)
```

Then in your `.env`:
```
JOB_DELETION_DAYS=14
```

### Change Check Frequency

Edit `src/app/services/job_cleanup_service.py` line ~134:

```python
job_cleanup_service = JobCleanupService(check_interval_hours=6)  # Check every 6 hours
```

---

## Manual Testing

### Test the Background Service

1. **Check if service is running:**
   - Look for startup logs when running `uvicorn src.app.main:app --reload`
   - Should see "Job cleanup service started"

2. **Create a test job:**
   ```python
   # In Python console or test script
   from datetime import datetime, timedelta
   from src.app.core.database import SessionLocal
   from src.app.models.user import Job
   
   db = SessionLocal()
   
   # Create a job that's 8 days old
   old_job = Job(
       permit_type="Test",
       job_review_status="posted",
       review_posted_at=datetime.utcnow() - timedelta(days=8)
   )
   db.add(old_job)
   db.commit()
   ```

3. **Wait for next hourly check or trigger manually:**
   - The service runs every hour
   - Or restart the server to trigger immediate check

4. **Verify deletion:**
   - Check logs for deletion message
   - Query database to confirm job is gone

---

## Troubleshooting

### Service Not Starting

**Check logs for:**
```
ERROR: Failed to start job cleanup service: ...
```

**Common causes:**
- Database connection issues
- Import errors in service module

**Solution:**
- Check database connection
- Verify all imports are correct

### Jobs Not Being Deleted

**Check:**
1. Is `review_posted_at` column present in database?
   ```sql
   SELECT column_name FROM information_schema.columns 
   WHERE table_name='jobs' AND column_name='review_posted_at';
   ```

2. Do jobs have the timestamp set?
   ```sql
   SELECT id, job_review_status, review_posted_at 
   FROM jobs 
   WHERE job_review_status='posted' 
   LIMIT 10;
   ```

3. Are jobs old enough (7+ days)?
   ```sql
   SELECT id, review_posted_at, 
          EXTRACT(DAY FROM (NOW() - review_posted_at)) as days_old
   FROM jobs 
   WHERE job_review_status='posted' 
     AND review_posted_at IS NOT NULL
   ORDER BY review_posted_at;
   ```

### Service Stops Unexpectedly

**Check logs for errors:**
```
ERROR: Error in job cleanup service: ...
```

The service is designed to continue running even if one cleanup iteration fails.

---

## Summary Table

| Action | Endpoint | Status Set | Timestamp Set? | Auto-Delete After 7 Days? |
|--------|----------|------------|----------------|---------------------------|
| Contractor uploads job | `POST /api/jobs/upload-contractor-job` | `pending` | ❌ No | ❌ No (not posted yet) |
| Admin bulk uploads jobs | `POST /api/jobs/bulk-upload` | `posted` | ✅ Yes | ✅ Yes |
| Admin approves pending job | `PATCH /admin/dashboard/ingested-jobs/{id}/post` | `posted` | ✅ Yes | ✅ Yes |

---

## Key Files

| File | Purpose |
|------|---------|
| `src/app/models/user.py` | Job model with `review_posted_at` column |
| `src/app/services/job_cleanup_service.py` | Background cleanup service |
| `src/app/main.py` | Startup/shutdown events for service |
| `src/app/api/endpoints/jobs.py` | Job creation endpoints |
| `src/app/api/endpoints/admin_dashboard.py` | Admin job approval endpoint |

---

## Questions?

For technical issues, check:
1. Server startup logs
2. Hourly cleanup logs  
3. Database schema (verify `review_posted_at` column exists)
4. Job status and timestamps in database
