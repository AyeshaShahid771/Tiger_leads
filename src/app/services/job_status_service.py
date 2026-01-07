"""
Background service to manage job statuses and cleanup expired jobs.
Runs every hour to:
1. Update job_review_status based on timing (scheduled -> posted, posted -> expired)
2. Delete jobs with 'expired' status
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JobStatusService:
    """Service to manage job statuses and cleanup expired jobs"""

    def __init__(self):
        self.task = None
        self.running = False
        self.interval_hours = 1  # Run every 1 hour

    async def start(self):
        """Start the job status service"""
        if self.running:
            logger.warning("Job status service is already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._run())
        logger.info(f"Job status service started (runs every {self.interval_hours} hour)")

    async def stop(self):
        """Stop the job status service"""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Job status service stopped")

    async def _run(self):
        """Main loop that runs every hour"""
        while self.running:
            try:
                await self._process_jobs()
            except Exception as e:
                logger.error(f"Error in job status service: {str(e)}")

            # Wait 1 hour before next run
            await asyncio.sleep(self.interval_hours * 3600)

    async def _process_jobs(self):
        """Process all jobs: update statuses and delete expired"""
        try:
            # Get database URL from environment
            database_url = os.getenv("DATABASE_URL")
            if not database_url:
                logger.error("DATABASE_URL not found in environment")
                return

            # Create engine and session
            engine = create_engine(database_url)
            Session = sessionmaker(bind=engine)
            session = Session()

            try:
                now = datetime.utcnow()
                logger.info(f"Starting job status processing at {now}")

                # 1. Update pending jobs to posted (if posting time has arrived)
                update_to_posted_query = text("""
                    UPDATE jobs
                    SET job_review_status = 'posted',
                        review_posted_at = :now
                    WHERE job_review_status = 'pending'
                    AND anchor_at IS NOT NULL
                    AND due_at IS NOT NULL
                    AND :now >= (anchor_at + (day_offset || ' days')::INTERVAL)
                    AND :now <= due_at
                    AND permit_status IN ('Ready to Issue', 'Issued', 'Submitted', 'In Review')
                """)
                result = session.execute(update_to_posted_query, {"now": now})
                posted_count = result.rowcount
                session.commit()
                logger.info(f"Updated {posted_count} jobs from 'pending' to 'posted'")

                # 2. Update posted/pending jobs to expired (if due_at has passed)
                update_to_expired_query = text("""
                    UPDATE jobs
                    SET job_review_status = 'expired'
                    WHERE job_review_status IN ('pending', 'posted')
                    AND due_at IS NOT NULL
                    AND :now > due_at
                """)
                result = session.execute(update_to_expired_query, {"now": now})
                expired_count = result.rowcount
                session.commit()
                logger.info(f"Updated {expired_count} jobs to 'expired'")

                # 3. Delete expired jobs
                delete_expired_query = text("""
                    DELETE FROM jobs
                    WHERE job_review_status = 'expired'
                """)
                result = session.execute(delete_expired_query)
                deleted_count = result.rowcount
                session.commit()
                logger.info(f"Deleted {deleted_count} expired jobs")

                logger.info(
                    f"Job status processing completed: "
                    f"{posted_count} posted, {expired_count} expired, {deleted_count} deleted"
                )

            finally:
                session.close()
                engine.dispose()

        except Exception as e:
            logger.error(f"Error processing jobs: {str(e)}")
            raise


# Create global instance
job_status_service = JobStatusService()
