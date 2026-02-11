# Database Migration - Quick Start Guide

## IMPORTANT: Read This First

This migration will transfer ALL data from your old Railway database to the new one.

**Estimated Time:** 30-45 minutes  
**Downtime Required:** Yes (15-20 minutes)

---

## Prerequisites

1. **Install PostgreSQL Tools**
   - Download from: https://www.postgresql.org/download/windows/
   - Or use existing installation
   - Verify: `pg_dump --version` and `pg_restore --version`

2. **Backup Current .env**
   ```powershell
   Copy-Item .env .env.backup
   ```

---

## Step 1: Create Database Dump (5 minutes)

```powershell
# Navigate to project directory
cd f:\Tiger_lead_backend

# Create dump file
pg_dump "postgresql://postgres:jgscsvYlKTLKhjKqVonzKcPebUnHDkdr@centerbeam.proxy.rlwy.net:43363/railway" --format=custom --file=tiger_leads_backup.dump --verbose --no-owner --no-acl
```

**Expected Output:**
- Progress messages showing tables being dumped
- Final file: `tiger_leads_backup.dump` (several MB)

---

## Step 2: Verify Dump (1 minute)

```powershell
# Check file exists and has size
Get-Item tiger_leads_backup.dump | Select-Object Name, Length
```

**Expected:** File size > 1 MB

---

## Step 3: Restore to New Database (10 minutes)

```powershell
# Restore dump to target database
pg_restore "postgresql://postgres:vubcsZDyBOcYidQCcypGPNoMrNmnGXuQ@yamanote.proxy.rlwy.net:37987/railway" --format=custom --verbose --no-owner --no-acl --clean --if-exists tiger_leads_backup.dump
```

**Expected Output:**
- Progress messages showing tables being created
- Some warnings are normal (e.g., "relation does not exist")
- Should complete without errors

---

## Step 4: Verify Migration (5 minutes)

```powershell
# Run verification script
.\Tiger_leads\Scripts\python.exe verify_migration.py
```

**Expected Output:**
```
✓ MATCH for all tables
✓✓✓ SUCCESS: ALL TABLES MIGRATED SUCCESSFULLY ✓✓✓
```

---

## Step 5: Verify Foreign Keys (2 minutes)

```powershell
# Check foreign keys
.\Tiger_leads\Scripts\python.exe verify_foreign_keys.py
```

**Expected:** List of all foreign key constraints

---

## Step 6: Verify Sequences (2 minutes)

```powershell
# Check sequences
.\Tiger_leads\Scripts\python.exe verify_sequences.py
```

**Expected:** List of all sequences with last values

---

## Step 7: Update .env File (1 minute)

Edit `f:\Tiger_lead_backend\.env`:

```env
# OLD DATABASE (comment out)
# DATABASE_URL=postgresql://postgres:jgscsvYlKTLKhjKqVonzKcPebUnHDkdr@centerbeam.proxy.rlwy.net:43363/railway

# NEW DATABASE (activate)
DATABASE_URL=postgresql://postgres:vubcsZDyBOcYidQCcypGPNoMrNmnGXuQ@yamanote.proxy.rlwy.net:37987/railway
```

---

## Step 8: Test Application (5 minutes)

```powershell
# Start application
uvicorn src.app.main:app --reload
```

**Test these endpoints:**
1. Login: `POST /auth/login`
2. Get jobs: `GET /jobs`
3. User profile: `GET /contractor/profile` or `GET /supplier/profile`

---

## Troubleshooting

### Error: "pg_dump: command not found"

**Solution:** Add PostgreSQL bin directory to PATH or use full path:
```powershell
"C:\Program Files\PostgreSQL\15\bin\pg_dump.exe" ...
```

### Error: "connection refused"

**Solution:** Check database URLs are correct and databases are accessible

### Error: "permission denied"

**Solution:** Verify database credentials are correct

### Verification shows mismatched counts

**Solution:**
1. Check for errors during restore
2. Re-run restore command
3. Contact support if issue persists

---

## Rollback Plan

If something goes wrong:

### Option 1: Restore from backup
```powershell
# Restore to old database
pg_restore "postgresql://postgres:jgscsvYlKTLKhjKqVonzKcPebUnHDkdr@centerbeam.proxy.rlwy.net:43363/railway" --format=custom --clean tiger_leads_backup.dump
```

### Option 2: Revert .env
```powershell
# Restore old .env
Copy-Item .env.backup .env
```

---

## Post-Migration Checklist

- [ ] All verification scripts pass
- [ ] Application starts without errors
- [ ] Users can log in
- [ ] Jobs are visible
- [ ] Subscriptions work
- [ ] No error logs
- [ ] .env updated to new database
- [ ] Old .env backed up

---

## Need Help?

- Check full migration plan: `database_migration_plan.md`
- Railway Support: https://railway.app/help
- PostgreSQL Docs: https://www.postgresql.org/docs/

---

**IMPORTANT:** Keep the `tiger_leads_backup.dump` file for at least 7 days after successful migration!
