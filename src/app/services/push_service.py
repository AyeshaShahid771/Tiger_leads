"""
Web Push Notification Service

Handles sending push notifications to users about new jobs.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from pywebpush import webpush, WebPushException
from sqlalchemy.orm import Session
from sqlalchemy import or_

from src.app.models.user import PushSubscription, User

logger = logging.getLogger(__name__)

# VAPID configuration
# Try to use private key file path first (for local development)
# Fall back to environment variable (for Vercel deployment)
VAPID_PRIVATE_KEY = None
vapid_key_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "vapid_private_key.pem")

if os.path.exists(vapid_key_path):
    # Pass the file path directly - pywebpush can handle PEM files
    VAPID_PRIVATE_KEY = vapid_key_path
    logger.info("VAPID private key loaded from vapid_private_key.pem")
else:
    # Fall back to environment variable if file not found
    env_key = os.getenv("VAPID_PRIVATE_KEY", "")
    if env_key:
        # Replace escaped newlines with actual newlines for proper key parsing
        VAPID_PRIVATE_KEY = env_key.replace("\\n", "\n")
        logger.info("VAPID private key loaded from environment variable")
    else:
        logger.warning("VAPID private key not found in file or environment variable")

VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY")
VAPID_CLAIM_EMAIL = os.getenv("VAPID_CLAIM_EMAIL", "mailto:admin@tigerleads.ai")


def send_push_notification(
    subscription: PushSubscription,
    title: str,
    body: str,
    icon: Optional[str] = None,
    url: Optional[str] = None,
    db: Optional[Session] = None
) -> bool:
    """
    Send a push notification to a single subscription.
    
    Args:
        subscription: PushSubscription model instance
        title: Notification title
        body: Notification body text
        icon: Optional icon URL
        url: Optional URL to open when clicked
        db: Optional database session for cleanup
    
    Returns:
        True if sent successfully, False otherwise
    """
    
    if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        logger.error("VAPID keys not configured. Cannot send push notifications.")
        return False
    
    subscription_info = {
        "endpoint": subscription.endpoint,
        "keys": {
            "p256dh": subscription.p256dh_key,
            "auth": subscription.auth_key
        }
    }
    
    payload = {
        "title": title,
        "body": body,
        "icon": icon or "https://tigerleads.ai/logo.png",
        "url": url or "https://tigerleads.ai"
    }
    
    try:
        # Extract the origin (scheme + host) from the endpoint for 'aud' claim
        from urllib.parse import urlparse
        parsed_endpoint = urlparse(subscription.endpoint)
        audience = f"{parsed_endpoint.scheme}://{parsed_endpoint.netloc}"
        
        # Validate that we have a proper audience URL
        if not parsed_endpoint.scheme or not parsed_endpoint.netloc:
            logger.warning(f"Skipping subscription {subscription.id} - invalid endpoint: {subscription.endpoint}")
            return False
        
        logger.info(f"Sending push to subscription {subscription.id} with aud={audience}")
        
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={
                "sub": VAPID_CLAIM_EMAIL,
                "aud": audience
            }
        )
        logger.info(f"Push notification sent to subscription {subscription.id} (user {subscription.user_id})")
        return True
        
    except WebPushException as e:
        logger.error(f"Failed to send push notification to subscription {subscription.id}: {e}")
        
        # If subscription is invalid/expired (404 or 410), delete it
        if e.response and e.response.status_code in [404, 410]:
            logger.info(f"Removing invalid subscription {subscription.id}")
            if db:
                try:
                    db.delete(subscription)
                    db.commit()
                    logger.info(f"Deleted expired subscription {subscription.id}")
                except Exception as delete_error:
                    logger.error(f"Failed to delete subscription: {delete_error}")
                    db.rollback()
        
        return False
    except ValueError as e:
        # VAPID key format error
        logger.error(f"ValueError sending push notification to subscription {subscription.id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending push notification: {e}")
        return False


def send_push_to_users(
    db: Session,
    user_ids: list[int],
    title: str,
    body: str,
    icon: Optional[str] = None,
    url: Optional[str] = None
) -> dict:
    """
    Send push notifications to multiple users.
    
    Args:
        db: Database session
        user_ids: List of user IDs to notify
        title: Notification title
        body: Notification body text
        icon: Optional icon URL
        url: Optional URL to open when clicked
    
    Returns:
        Dictionary with stats: total, success, failed
    """
    
    subscriptions = (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id.in_(user_ids))
        .all()
    )
    
    success_count = 0
    failed_count = 0
    
    for subscription in subscriptions:
        if send_push_notification(subscription, title, body, icon, url, db):
            success_count += 1
        else:
            failed_count += 1
    
    logger.info(f"Push notification batch: {success_count} sent, {failed_count} failed out of {len(subscriptions)} total")
    
    return {
        "total": len(subscriptions),
        "success": success_count,
        "failed": failed_count
    }


def send_weekly_job_notifications(db: Session) -> dict:
    """
    Send weekly job notifications to users who haven't been notified in 7+ days.
    
    This function:
    1. Finds subscriptions that haven't been notified in 7+ days
    2. Sends push notification about new jobs
    3. Updates last_notified_at timestamp
    
    Args:
        db: Database session
    
    Returns:
        Dictionary with stats: checked, notified, skipped
    """
    
    # Get subscriptions that need weekly notification
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    
    subscriptions = (
        db.query(PushSubscription)
        .filter(
            or_(
                PushSubscription.last_notified_at == None,
                PushSubscription.last_notified_at <= seven_days_ago
            )
        )
        .all()
    )
    
    logger.info(f"Found {len(subscriptions)} subscriptions eligible for weekly notification")
    
    notified_count = 0
    skipped_count = 0
    
    for subscription in subscriptions:
        # Send notification
        success = send_push_notification(
            subscription=subscription,
            title="New Jobs Available!",
            body="We have new jobs that match your profile. Check them out now!",
            icon="https://tigerleads.ai/job-icon.png",
            url="https://tigerleads.ai/jobs",
            db=db
        )
        
        if success:
            # Update last notified timestamp
            subscription.last_notified_at = datetime.utcnow()
            db.commit()
            notified_count += 1
            logger.info(f"Sent weekly notification to user {subscription.user_id}")
        else:
            skipped_count += 1
    
    logger.info(f"Weekly job notifications: {notified_count} sent, {skipped_count} skipped")
    
    return {
        "checked": len(subscriptions),
        "notified": notified_count,
        "skipped": skipped_count
    }
