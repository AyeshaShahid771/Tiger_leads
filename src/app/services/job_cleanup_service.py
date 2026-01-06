"""
Background Job Cleanup Service

This service runs automatically in the background when the FastAPI application starts.
It checks every hour for jobs that need to be deleted (7 days after being posted).
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
        await self._cleanup_old_jobs()
        
        while self.is_running:
            try:
                # Wait for the interval
                await asyncio.sleep(self.check_interval_hours * 3600)
                
                # Run cleanup
                await self._cleanup_old_jobs()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in job cleanup service: {str(e)}")
                # Continue running even if one iteration fails
    
    async def _cleanup_old_jobs(self):
        """Delete jobs that are 7 days old or more.
        
        NOTE: This functionality is currently DISABLED.
        The review_posted_at column is still tracked for future use.
        """
        db: Session = SessionLocal()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=7)
            
            logger.info("[Job Cleanup] Job deletion is DISABLED - review_posted_at still being tracked")
            
            # DISABLED: Job deletion logic commented out
            # Find jobs to delete
            # jobs_to_delete = db.query(models.user.Job).filter(
            #     models.user.Job.job_review_status == "posted",
            #     models.user.Job.review_posted_at.isnot(None),
            #     models.user.Job.review_posted_at <= cutoff_date
            # ).all()
            # 
            # if not jobs_to_delete:
            #     logger.info("[Job Cleanup] No jobs to delete")
            #     return
            # 
            # count = len(jobs_to_delete)
            # deleted_ids = []
            # 
            # # Delete jobs
            # for job in jobs_to_delete:
            #     deleted_ids.append(job.id)
            #     db.delete(job)
            # 
            # db.commit()
            # 
            # logger.info(f"[Job Cleanup] ✓ Successfully deleted {count} jobs")
            # logger.info(f"[Job Cleanup] Deleted job IDs: {deleted_ids[:20]}{'...' if len(deleted_ids) > 20 else ''}")
            
        except Exception as e:
            db.rollback()
            logger.error(f"[Job Cleanup] Error during cleanup: {str(e)}")
        finally:
            db.close()


# Global service instance
job_cleanup_service = JobCleanupService(check_interval_hours=1)
