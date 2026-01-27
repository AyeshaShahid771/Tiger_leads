"""
Background Job Cleanup Service

This service runs automatically in the background when the FastAPI application starts.
It checks every hour for jobs that need to be deleted based on user type unlock count.
Jobs are deleted when 5 or more users of the SAME user type have unlocked them
(e.g., 5 electricians, or 5 plumbers, etc.).
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.app import models
from src.app.core.database import SessionLocal

logger = logging.getLogger("uvicorn.error")


class JobCleanupService:
    """Background service for automatic job cleanup."""
    
    def __init__(self, check_interval_hours: int = 1):
        """
        Initialize the cleanup service.
        
        Args:
            check_interval_hours: How often to check for jobs to delete (default: every 1 hour)
        """
        self.check_interval_hours = check_interval_hours
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the background cleanup service."""
        if self.is_running:
            logger.warning("Job cleanup service is already running")
            return
        
        self.is_running = True
        self._task = asyncio.create_task(self._run())
        logger.info(f"Job cleanup service started (checking every {self.check_interval_hours} hour(s))")
    
    async def stop(self):
        """Stop the background cleanup service."""
        if not self.is_running:
            return
        
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Job cleanup service stopped")
    
    async def _run(self):
        """Main loop that runs the cleanup periodically."""
        # Run immediately on startup, then every interval
        await self._cleanup_jobs_by_unlock_count()
        await self._cleanup_temp_documents()
        
        while self.is_running:
            try:
                # Wait for the interval
                await asyncio.sleep(self.check_interval_hours * 3600)
                
                # Run cleanup
                await self._cleanup_jobs_by_unlock_count()
                await self._cleanup_temp_documents()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in job cleanup service: {str(e)}")
                # Continue running even if one iteration fails
    
    async def _cleanup_jobs_by_unlock_count(self):
        """Delete jobs that have been unlocked by 5 or more users of the SAME user type.
        
        This ensures jobs are removed when they've been accessed by enough users
        of a single type (e.g., 5 electricians, or 5 plumbers), indicating the
        lead has been widely distributed within that user type category.
        """
        db: Session = SessionLocal()
        try:
            logger.info("[Job Cleanup] Starting unlock-based cleanup check (by user type)")
            
            # Find jobs where ANY single user type has 5 or more unlocks
            # This query:
            # 1. Joins unlocked_leads with users to get user_id
            # 2. Joins with contractors and suppliers to get user_type arrays
            # 3. Unnests the user_type arrays to get individual types
            # 4. Groups by job_id AND user_type
            # 5. Counts distinct users per user type
            # 6. Returns jobs where ANY user type has 5+ distinct users
            query = text("""
                WITH user_types_unlocked AS (
                    SELECT 
                        ul.job_id,
                        ul.user_id,
                        UNNEST(COALESCE(c.user_type, s.user_type, ARRAY[]::text[])) as user_type
                    FROM unlocked_leads ul
                    INNER JOIN users u ON ul.user_id = u.id
                    LEFT JOIN contractors c ON u.id = c.user_id
                    LEFT JOIN suppliers s ON u.id = s.user_id
                    WHERE c.user_type IS NOT NULL OR s.user_type IS NOT NULL
                ),
                user_type_counts AS (
                    SELECT 
                        job_id,
                        user_type,
                        COUNT(DISTINCT user_id) as user_count
                    FROM user_types_unlocked
                    GROUP BY job_id, user_type
                )
                SELECT DISTINCT
                    job_id,
                    MAX(user_count) as max_users_in_type,
                    STRING_AGG(user_type || ':' || user_count::text, ', ' ORDER BY user_count DESC) as type_breakdown
                FROM user_type_counts
                WHERE user_count >= 5
                GROUP BY job_id
            """)
            
            result = db.execute(query)
            jobs_to_delete = result.fetchall()
            
            if not jobs_to_delete:
                logger.info("[Job Cleanup] No jobs to delete (no user type has 5+ users)")
                return
            
            count = len(jobs_to_delete)
            deleted_ids = []
            completed_ids = []
            
            # Process jobs that meet the threshold
            for row in jobs_to_delete:
                job_id = row.job_id
                max_users = row.max_users_in_type
                breakdown = row.type_breakdown
                
                # Get the job
                job = db.query(models.user.Job).filter(models.user.Job.id == job_id).first()
                if job:
                    # If uploaded by contractor, mark as Complete instead of deleting
                    if job.uploaded_by_contractor:
                        job.job_review_status = "Complete"
                        completed_ids.append(job_id)
                        logger.debug(f"[Job Cleanup] Marking contractor job {job_id} as Complete (max {max_users} users in one type: {breakdown})")
                    else:
                        # Delete non-contractor jobs
                        deleted_ids.append(job_id)
                        db.delete(job)
                        logger.debug(f"[Job Cleanup] Deleting job {job_id} (max {max_users} users in one type: {breakdown})")
            
            db.commit()
            
            # Log summary
            if deleted_ids:
                logger.info(f"[Job Cleanup] ✓ Successfully deleted {len(deleted_ids)} jobs (5+ users in same type)")
                logger.info(f"[Job Cleanup] Deleted job IDs: {deleted_ids[:20]}{'...' if len(deleted_ids) > 20 else ''}")
            
            if completed_ids:
                logger.info(f"[Job Cleanup] ✓ Successfully marked {len(completed_ids)} contractor jobs as Complete (5+ users in same type)")
                logger.info(f"[Job Cleanup] Completed job IDs: {completed_ids[:20]}{'...' if len(completed_ids) > 20 else ''}")
            
            if not deleted_ids and not completed_ids:
                logger.info(f"[Job Cleanup] No jobs processed (found {count} candidates but none were valid)")
            
        except Exception as e:
            db.rollback()
            logger.error(f"[Job Cleanup] Error during cleanup: {str(e)}")
        finally:
            db.close()
    
    async def _cleanup_temp_documents(self):
        """Delete expired temporary documents that are not linked to jobs or drafts."""
        db: Session = SessionLocal()
        try:
            now = datetime.utcnow()
            
            # Find expired temp documents that are not linked to jobs or drafts
            expired_docs = db.query(models.user.TempDocument).filter(
                models.user.TempDocument.expires_at <= now,
                models.user.TempDocument.linked_to_job == False,
                models.user.TempDocument.linked_to_draft == False
            ).all()
            
            if not expired_docs:
                logger.info("[Temp Docs Cleanup] No expired temp documents to delete")
                return
            
            count = len(expired_docs)
            deleted_ids = []
            
            # Delete expired temp documents
            for doc in expired_docs:
                deleted_ids.append(doc.temp_upload_id)
                db.delete(doc)
            
            db.commit()
            
            logger.info(f"[Temp Docs Cleanup] ✓ Successfully deleted {count} expired temp documents")
            logger.info(f"[Temp Docs Cleanup] Deleted IDs: {deleted_ids[:10]}{'...' if len(deleted_ids) > 10 else ''}")
            
        except Exception as e:
            db.rollback()
            logger.error(f"[Temp Docs Cleanup] Error during cleanup: {str(e)}")
        finally:
            db.close()


# Global service instance
job_cleanup_service = JobCleanupService(check_interval_hours=1)
