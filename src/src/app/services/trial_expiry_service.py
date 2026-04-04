"""
Background service to automatically expire trial credits after 14 days.

This service runs daily and:
- Checks for trial subscribers whose trial_credits_expires_at has passed
- Sets current_credits to 0 if they haven't upgraded to paid subscription
- Keeps trial_credits_used flag for tracking purposes
"""

import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.app.models.user import Subscriber
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment variables")

# Create database session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class TrialExpiryService:
    """Background service to expire trial credits after 14 days."""
    
    def __init__(self):
        self.running = False
        self.task = None
    
    async def start(self):
        """Start the background service."""
        if self.running:
            logger.warning("Trial expiry service is already running")
            return
        
        self.running = True
        self.task = asyncio.create_task(self._run_expiry_loop())
        logger.info("Trial expiry service started")
    
    async def stop(self):
        """Stop the background service."""
        if not self.running:
            return
        
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Trial expiry service stopped")
    
    async def _run_expiry_loop(self):
        """Main loop that checks for expired trials daily."""
        while self.running:
            try:
                await self._expire_trial_credits()
                
                # Wait 24 hours before next check
                await asyncio.sleep(86400)  # 24 hours in seconds
                
            except asyncio.CancelledError:
                logger.info("Trial expiry service loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in trial expiry loop: {str(e)}", exc_info=True)
                # Wait 1 hour before retrying on error
                await asyncio.sleep(3600)
    
    async def _expire_trial_credits(self):
        """Expire trial credits for subscribers whose trial period has ended."""
        db: Session = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            
            # Find subscribers with expired trials still on trial status
            expired_trials = db.query(Subscriber).filter(
                Subscriber.subscription_status == "trial",
                Subscriber.trial_credits_expires_at <= now,
                Subscriber.current_credits > 0
            ).all()
            
            if not expired_trials:
                logger.info("No expired trials found")
                return
            
            expired_count = 0
            for subscriber in expired_trials:
                # Zero out credits for expired trials
                credits_removed = subscriber.current_credits
                subscriber.current_credits = 0
                subscriber.is_active = False
                subscriber.subscription_status = "trial_expired"
                
                logger.info(
                    f"Expired trial for subscriber {subscriber.id}: "
                    f"Removed {credits_removed} credits"
                )
                expired_count += 1
            
            db.commit()
            logger.info(f"Expired {expired_count} trial subscriptions")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error expiring trial credits: {str(e)}", exc_info=True)
            raise
        finally:
            db.close()


# Global instance
trial_expiry_service = TrialExpiryService()


async def start_trial_expiry_service():
    """Start the trial expiry background service."""
    await trial_expiry_service.start()


async def stop_trial_expiry_service():
    """Stop the trial expiry background service."""
    await trial_expiry_service.stop()
