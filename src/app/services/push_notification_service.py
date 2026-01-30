"""
Background Push Notification Service

This service runs automatically in the background when the FastAPI application starts.
It sends weekly job notifications to users every 7 days.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from src.app.core.database import SessionLocal
from src.app.services.push_service import send_weekly_job_notifications

logger = logging.getLogger("uvicorn.error")


class PushNotificationService:
    """Background service for automatic push notifications."""
    
    def __init__(self, check_interval_days: int = 7):
        """
        Initialize the push notification service.
        
        Args:
            check_interval_days: How often to send notifications (default: every 7 days)
        """
        self.check_interval_days = check_interval_days
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the background push notification service."""
        if self.is_running:
            logger.warning("Push notification service is already running")
            return
        
        self.is_running = True
        self._task = asyncio.create_task(self._run())
        logger.info(f"Push notification service started (sending every {self.check_interval_days} day(s))")
    
    async def stop(self):
        """Stop the background push notification service."""
        if not self.is_running:
            return
        
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Push notification service stopped")
    
    async def _run(self):
        """Main loop that sends notifications periodically."""
        # Run immediately on startup, then every interval
        await self._send_weekly_notifications()
        
        while self.is_running:
            try:
                # Wait for the interval (7 days = 7 * 24 * 3600 seconds)
                await asyncio.sleep(self.check_interval_days * 24 * 3600)
                
                # Send notifications
                await self._send_weekly_notifications()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in push notification service: {str(e)}")
                # Continue running even if one iteration fails
    
    async def _send_weekly_notifications(self):
        """Send weekly job notifications to eligible users."""
        db: Session = SessionLocal()
        try:
            logger.info("[Push Notifications] Starting weekly job notification check")
            
            # Call the send_weekly_job_notifications function
            result = send_weekly_job_notifications(db)
            
            logger.info(
                f"[Push Notifications] ✓ Completed: "
                f"{result['notified']} sent, {result['skipped']} skipped "
                f"out of {result['checked']} checked"
            )
            
        except Exception as e:
            logger.error(f"[Push Notifications] Error during notification send: {str(e)}")
        finally:
            db.close()


# Global service instance - runs every 7 days
push_notification_service = PushNotificationService(check_interval_days=7)
