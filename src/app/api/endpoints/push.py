"""
Web Push Notification Endpoints

Endpoints for managing push notification subscriptions and sending notifications.
"""

import os
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.app import models
from src.app.schemas.push import (
    VapidPublicKeyResponse,
    PushSubscriptionRequest,
    PushSubscriptionResponse,
    UnsubscribeRequest
)
from src.app.api.deps import get_current_user
from src.app.core.database import get_db
from src.app.services.push_service import send_push_notification

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/push", tags=["Push Notifications"])


@router.get("/vapid-public-key", response_model=VapidPublicKeyResponse)
def get_vapid_public_key():
    """
    Get VAPID public key for frontend subscription.
    
    The frontend needs this key to subscribe users to push notifications.
    No authentication required.
    """
    public_key = os.getenv("VAPID_PUBLIC_KEY")
    
    if not public_key:
        raise HTTPException(
            status_code=500,
            detail="VAPID public key not configured"
        )
    
    return VapidPublicKeyResponse(public_key=public_key)


@router.post("/subscribe", response_model=PushSubscriptionResponse)
def subscribe_to_push(
    data: PushSubscriptionRequest,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Save user's push notification subscription.
    
    When a user opts-in to receive push notifications, the frontend
    sends their subscription details here to be stored in the database.
    """
    
    logger.info(f"Push subscription request from user {current_user.id} ({current_user.email})")
    
    # Check if subscription already exists for this endpoint
    existing = (
        db.query(models.user.PushSubscription)
        .filter(models.user.PushSubscription.endpoint == data.endpoint)
        .first()
    )
    
    if existing:
        # Update existing subscription (user might have re-subscribed)
        logger.info(f"Updating existing subscription {existing.id}")
        existing.p256dh_key = data.keys.p256dh
        existing.auth_key = data.keys.auth
        existing.user_agent = data.user_agent
        existing.user_id = current_user.id  # Update user_id in case it changed
    else:
        # Create new subscription
        logger.info(f"Creating new push subscription for user {current_user.id}")
        subscription = models.user.PushSubscription(
            user_id=current_user.id,
            endpoint=data.endpoint,
            p256dh_key=data.keys.p256dh,
            auth_key=data.keys.auth,
            user_agent=data.user_agent
        )
        db.add(subscription)
    
    db.commit()
    
    logger.info(f"Push subscription saved successfully for user {current_user.id}")
    
    return PushSubscriptionResponse(
        message="Subscription saved successfully. You will receive notifications about new jobs every 7 days."
    )


@router.delete("/unsubscribe", response_model=PushSubscriptionResponse)
def unsubscribe_from_push(
    data: UnsubscribeRequest,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Remove user's push notification subscription.
    
    When a user opts-out of push notifications, this endpoint
    removes their subscription from the database.
    """
    
    logger.info(f"Unsubscribe request from user {current_user.id}")
    
    subscription = (
        db.query(models.user.PushSubscription)
        .filter(
            models.user.PushSubscription.user_id == current_user.id,
            models.user.PushSubscription.endpoint == data.endpoint
        )
        .first()
    )
    
    if not subscription:
        logger.warning(f"Subscription not found for user {current_user.id}")
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    db.delete(subscription)
    db.commit()
    
    logger.info(f"Unsubscribed user {current_user.id} from push notifications")
    
    return PushSubscriptionResponse(
        message="Unsubscribed successfully. You will no longer receive push notifications."
    )


@router.post("/test", response_model=PushSubscriptionResponse)
def send_test_notification(
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Send a test push notification to the current user.
    
    Useful for testing if push notifications are working correctly.
    """
    
    logger.info(f"Test notification request from user {current_user.id}")
    
    # Get user's subscriptions
    subscriptions = (
        db.query(models.user.PushSubscription)
        .filter(models.user.PushSubscription.user_id == current_user.id)
        .all()
    )
    
    if not subscriptions:
        raise HTTPException(
            status_code=404,
            detail="No push subscriptions found. Please subscribe first."
        )
    
    # Send test notification to all user's subscriptions
    success_count = 0
    for subscription in subscriptions:
        if send_push_notification(
            subscription=subscription,
            title="Test Notification",
            body="This is a test notification from Tiger Leads!",
            icon="https://tigerleads.ai/logo.png",
            url="https://tigerleads.ai",
            db=db
        ):
            success_count += 1
    
    if success_count == 0:
        raise HTTPException(
            status_code=500,
            detail="Failed to send test notification. Please check your subscription."
        )
    
    logger.info(f"Sent test notification to {success_count} subscription(s)")
    
    return PushSubscriptionResponse(
        message=f"Test notification sent successfully to {success_count} device(s)!"
    )

