import csv
import io
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from src.app import models, schemas
from src.app.api.deps import get_current_user
from src.app.core.database import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscription", tags=["Subscription"])


@router.get("/plans", response_model=List[schemas.subscription.SubscriptionResponse])
def get_subscription_plans(db: Session = Depends(get_db)):
    """Get all available subscription plans."""
    subscriptions = db.query(models.user.Subscription).all()
    return subscriptions


@router.post("/subscribe", response_model=schemas.subscription.SubscriberResponse)
def subscribe_to_plan(
    data: schemas.subscription.SubscriberCreate,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Subscribe user to a plan."""
    # Check if subscription exists
    subscription = (
        db.query(models.user.Subscription)
        .filter(models.user.Subscription.id == data.subscription_id)
        .first()
    )

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription plan not found")

    # Get or create subscriber record
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.user_id == current_user.id)
        .first()
    )

    if not subscriber:
        subscriber = models.user.Subscriber(
            user_id=current_user.id,
            subscription_id=data.subscription_id,
            current_credits=subscription.tokens,
            subscription_start_date=datetime.now(),
            subscription_renew_date=datetime.now() + timedelta(days=30),
            is_active=True,
        )
        db.add(subscriber)
    else:
        # Update existing subscription
        subscriber.subscription_id = data.subscription_id
        subscriber.current_credits += subscription.tokens
        subscriber.subscription_start_date = datetime.now()
        subscriber.subscription_renew_date = datetime.now() + timedelta(days=30)
        subscriber.is_active = True

    db.commit()
    db.refresh(subscriber)

    logger.info(
        f"User {current_user.email} subscribed to {subscription.name} plan"
    )
    return subscriber


@router.get("/my-subscription", response_model=schemas.subscription.SubscriberResponse)
def get_my_subscription(
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user's subscription details."""
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.user_id == current_user.id)
        .first()
    )

    if not subscriber:
        raise HTTPException(
            status_code=404, detail="No subscription found for this user"
        )

    return subscriber


@router.get("/wallet")
def get_wallet_info(
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user's wallet information including credits and spending history."""
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.user_id == current_user.id)
        .first()
    )

    if not subscriber:
        return {
            "current_credits": 0,
            "total_spending": 0,
            "subscription": None,
            "subscription_renew_date": None,
            "unlocked_leads": [],
        }

    # Get subscription details
    subscription = None
    if subscriber.subscription_id:
        subscription = (
            db.query(models.user.Subscription)
            .filter(models.user.Subscription.id == subscriber.subscription_id)
            .first()
        )

    # Get unlocked leads with spending details
    unlocked_leads = (
        db.query(models.user.UnlockedLead)
        .filter(models.user.UnlockedLead.user_id == current_user.id)
        .order_by(models.user.UnlockedLead.unlocked_at.desc())
        .limit(50)
        .all()
    )

    spending_history = [
        {
            "job_id": lead.job_id,
            "credits_spent": lead.credits_spent,
            "unlocked_at": lead.unlocked_at,
        }
        for lead in unlocked_leads
    ]

    return {
        "current_credits": subscriber.current_credits,
        "total_spending": subscriber.total_spending,
        "subscription": subscription.name if subscription else None,
        "subscription_renew_date": subscriber.subscription_renew_date,
        "spending_history": spending_history,
    }
