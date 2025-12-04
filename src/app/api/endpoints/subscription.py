import csv
import io
import json
import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional

import stripe
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from src.app import models, schemas
from src.app.api.deps import get_current_user
from src.app.core.database import get_db
from src.app.utils.team_helpers import get_effective_user_id

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://tigerleads.vercel.app")

router = APIRouter(prefix="/subscription", tags=["Subscription"])


@router.get("/plans", response_model=List[schemas.subscription.SubscriptionResponse])
def get_subscription_plans(db: Session = Depends(get_db)):
    """Get all available subscription plans."""
    subscriptions = db.query(models.user.Subscription).all()
    return subscriptions


@router.post(
    "/create-checkout-session",
    response_model=schemas.subscription.CreateCheckoutSessionResponse,
)
async def create_checkout_session(
    data: schemas.subscription.CreateCheckoutSessionRequest,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a Stripe Checkout session for first-time subscription.

    This endpoint:
    1. Gets the subscription plan details from database
    2. Creates or retrieves Stripe customer for the user
    3. Creates a Stripe Checkout session
    4. Returns the checkout URL for frontend to redirect user
    """
    # Only main accounts can subscribe (sub-users share main account's subscription)
    if current_user.parent_user_id:
        raise HTTPException(
            status_code=403,
            detail="Sub-users cannot create subscriptions. The main account owner manages subscriptions.",
        )

    # Check if subscription plan exists
    subscription_plan = (
        db.query(models.user.Subscription)
        .filter(models.user.Subscription.id == data.subscription_id)
        .first()
    )

    if not subscription_plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")

    if not subscription_plan.stripe_price_id:
        raise HTTPException(
            status_code=400,
            detail="This subscription plan is not configured with Stripe. Please contact support.",
        )

    try:
        # Create or retrieve Stripe customer
        if not current_user.stripe_customer_id:
            # Create new Stripe customer
            customer = stripe.Customer.create(
                email=current_user.email,
                metadata={"user_id": current_user.id, "user_email": current_user.email},
            )
            current_user.stripe_customer_id = customer.id
            db.commit()
            logger.info(
                f"Created Stripe customer {customer.id} for user {current_user.email}"
            )
        else:
            # Retrieve existing customer
            customer = stripe.Customer.retrieve(current_user.stripe_customer_id)
            logger.info(f"Using existing Stripe customer {customer.id}")

        # Create Checkout Session
        checkout_session = stripe.checkout.Session.create(
            customer=customer.id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price": subscription_plan.stripe_price_id,
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url=f"{FRONTEND_URL}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/subscription/cancel",
            metadata={
                "user_id": current_user.id,
                "subscription_plan_id": subscription_plan.id,
                "user_email": current_user.email,
            },
            subscription_data={
                "metadata": {
                    "user_id": current_user.id,
                    "subscription_plan_id": subscription_plan.id,
                }
            },
        )

        logger.info(
            f"Created checkout session {checkout_session.id} for user {current_user.email}"
        )

        return {"checkout_url": checkout_session.url, "session_id": checkout_session.id}

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create checkout session: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error creating checkout session: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while creating checkout session",
        )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: Session = Depends(get_db),
):
    """
    Handle Stripe webhook events.

    This endpoint receives notifications from Stripe about:
    - checkout.session.completed: First payment successful
    - invoice.payment_succeeded: Monthly renewal successful
    - invoice.payment_failed: Payment failed
    - customer.subscription.deleted: Subscription canceled
    """
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        logger.error(f"Invalid payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    logger.info(f"Received Stripe webhook event: {event['type']}")

    # Handle different event types
    if event["type"] == "checkout.session.completed":
        await handle_checkout_session_completed(event["data"]["object"], db)

    elif event["type"] == "invoice.payment_succeeded":
        await handle_invoice_payment_succeeded(event["data"]["object"], db)

    elif event["type"] == "invoice.payment_failed":
        await handle_invoice_payment_failed(event["data"]["object"], db)

    elif event["type"] == "customer.subscription.deleted":
        await handle_subscription_deleted(event["data"]["object"], db)

    elif event["type"] == "customer.subscription.updated":
        await handle_subscription_updated(event["data"]["object"], db)

    return {"status": "success"}


async def handle_checkout_session_completed(session, db: Session):
    """Handle successful checkout (first-time subscription)."""
    logger.info(f"Processing checkout.session.completed for session {session['id']}")

    user_id = int(session["metadata"]["user_id"])
    subscription_plan_id = int(session["metadata"]["subscription_plan_id"])
    stripe_subscription_id = session["subscription"]

    # Get user and subscription plan
    user = db.query(models.user.User).filter(models.user.User.id == user_id).first()
    subscription_plan = (
        db.query(models.user.Subscription)
        .filter(models.user.Subscription.id == subscription_plan_id)
        .first()
    )

    if not user or not subscription_plan:
        logger.error(f"User or subscription plan not found for session {session['id']}")
        return

    # Get or create subscriber record
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.user_id == user_id)
        .first()
    )

    if not subscriber:
        subscriber = models.user.Subscriber(
            user_id=user_id,
            subscription_id=subscription_plan_id,
            current_credits=subscription_plan.credits,
            seats_used=1,
            subscription_start_date=datetime.utcnow(),
            subscription_renew_date=datetime.utcnow() + timedelta(days=30),
            is_active=True,
            stripe_subscription_id=stripe_subscription_id,
            subscription_status="active",
        )
        db.add(subscriber)
    else:
        # Update existing subscriber
        subscriber.subscription_id = subscription_plan_id
        subscriber.current_credits = subscription_plan.credits
        subscriber.subscription_start_date = datetime.utcnow()
        subscriber.subscription_renew_date = datetime.utcnow() + timedelta(days=30)
        subscriber.is_active = True
        subscriber.stripe_subscription_id = stripe_subscription_id
        subscriber.subscription_status = "active"

    db.commit()

    logger.info(
        f"Activated {subscription_plan.name} subscription for user {user.email}. "
        f"Credits: {subscription_plan.credits}, Max seats: {subscription_plan.max_seats}"
    )

    # TODO: Send welcome email to user


async def handle_invoice_payment_succeeded(invoice, db: Session):
    """Handle successful monthly renewal payment."""
    logger.info(f"Processing invoice.payment_succeeded for invoice {invoice['id']}")

    stripe_subscription_id = invoice["subscription"]

    if not stripe_subscription_id:
        logger.warning(f"No subscription ID in invoice {invoice['id']}")
        return

    # Find subscriber by Stripe subscription ID
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.stripe_subscription_id == stripe_subscription_id)
        .first()
    )

    if not subscriber:
        logger.error(
            f"Subscriber not found for Stripe subscription {stripe_subscription_id}"
        )
        return

    # Get subscription plan
    subscription_plan = (
        db.query(models.user.Subscription)
        .filter(models.user.Subscription.id == subscriber.subscription_id)
        .first()
    )

    if not subscription_plan:
        logger.error(f"Subscription plan not found for subscriber {subscriber.id}")
        return

    # Reset credits for the new month and update renewal date
    subscriber.current_credits = subscription_plan.credits
    subscriber.subscription_renew_date = datetime.utcnow() + timedelta(days=30)
    subscriber.is_active = True
    subscriber.subscription_status = "active"

    db.commit()

    # Get user for logging
    user = (
        db.query(models.user.User)
        .filter(models.user.User.id == subscriber.user_id)
        .first()
    )

    logger.info(
        f"Renewed subscription for user {user.email if user else subscriber.user_id}. "
        f"Credits reset to {subscription_plan.credits}"
    )

    # TODO: Send renewal confirmation email


async def handle_invoice_payment_failed(invoice, db: Session):
    """Handle failed payment."""
    logger.info(f"Processing invoice.payment_failed for invoice {invoice['id']}")

    stripe_subscription_id = invoice["subscription"]

    if not stripe_subscription_id:
        logger.warning(f"No subscription ID in failed invoice {invoice['id']}")
        return

    # Find subscriber
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.stripe_subscription_id == stripe_subscription_id)
        .first()
    )

    if not subscriber:
        logger.error(
            f"Subscriber not found for Stripe subscription {stripe_subscription_id}"
        )
        return

    # Mark subscription as past_due
    subscriber.subscription_status = "past_due"
    subscriber.is_active = False  # Suspend access

    db.commit()

    # Get user
    user = (
        db.query(models.user.User)
        .filter(models.user.User.id == subscriber.user_id)
        .first()
    )

    logger.warning(
        f"Payment failed for user {user.email if user else subscriber.user_id}. Subscription marked as past_due."
    )

    # TODO: Send payment failure email with retry instructions


async def handle_subscription_deleted(subscription_obj, db: Session):
    """Handle subscription cancellation."""
    logger.info(
        f"Processing customer.subscription.deleted for subscription {subscription_obj['id']}"
    )

    stripe_subscription_id = subscription_obj["id"]

    # Find subscriber
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.stripe_subscription_id == stripe_subscription_id)
        .first()
    )

    if not subscriber:
        logger.error(
            f"Subscriber not found for Stripe subscription {stripe_subscription_id}"
        )
        return

    # Cancel subscription
    subscriber.is_active = False
    subscriber.subscription_status = "canceled"
    subscriber.subscription_id = None
    subscriber.stripe_subscription_id = None

    db.commit()

    # Get user
    user = (
        db.query(models.user.User)
        .filter(models.user.User.id == subscriber.user_id)
        .first()
    )

    logger.info(
        f"Canceled subscription for user {user.email if user else subscriber.user_id}"
    )

    # TODO: Send cancellation confirmation email


async def handle_subscription_updated(subscription_obj, db: Session):
    """Handle subscription status updates."""
    logger.info(
        f"Processing customer.subscription.updated for subscription {subscription_obj['id']}"
    )

    stripe_subscription_id = subscription_obj["id"]
    status = subscription_obj["status"]

    # Find subscriber
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.stripe_subscription_id == stripe_subscription_id)
        .first()
    )

    if not subscriber:
        logger.error(
            f"Subscriber not found for Stripe subscription {stripe_subscription_id}"
        )
        return

    # Update subscription status
    subscriber.subscription_status = status

    # Update active status based on Stripe status
    if status in ["active", "trialing"]:
        subscriber.is_active = True
    elif status in ["past_due", "canceled", "unpaid"]:
        subscriber.is_active = False

    db.commit()

    logger.info(
        f"Updated subscription status to {status} for subscriber {subscriber.id}"
    )


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


@router.post("/cancel-subscription")
async def cancel_subscription(
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Cancel the current subscription.

    The subscription will remain active until the end of the current billing period.
    """
    # Only main accounts can cancel subscriptions
    if current_user.parent_user_id:
        raise HTTPException(
            status_code=403,
            detail="Only the main account owner can cancel subscriptions",
        )

    # Get subscriber
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.user_id == current_user.id)
        .first()
    )

    if not subscriber or not subscriber.stripe_subscription_id:
        raise HTTPException(status_code=404, detail="No active subscription found")

    try:
        # Cancel the Stripe subscription at period end
        stripe.Subscription.modify(
            subscriber.stripe_subscription_id, cancel_at_period_end=True
        )

        logger.info(
            f"Scheduled cancellation for subscription {subscriber.stripe_subscription_id}"
        )

        return {
            "message": "Subscription will be canceled at the end of the current billing period",
            "renew_date": subscriber.subscription_renew_date,
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error canceling subscription: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to cancel subscription: {str(e)}"
        )


@router.post("/reactivate-subscription")
async def reactivate_subscription(
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Reactivate a subscription that was scheduled for cancellation.
    """
    # Only main accounts can reactivate subscriptions
    if current_user.parent_user_id:
        raise HTTPException(
            status_code=403,
            detail="Only the main account owner can reactivate subscriptions",
        )

    # Get subscriber
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.user_id == current_user.id)
        .first()
    )

    if not subscriber or not subscriber.stripe_subscription_id:
        raise HTTPException(status_code=404, detail="No subscription found")

    try:
        # Remove the cancellation schedule
        stripe.Subscription.modify(
            subscriber.stripe_subscription_id, cancel_at_period_end=False
        )

        logger.info(f"Reactivated subscription {subscriber.stripe_subscription_id}")

        return {
            "message": "Subscription has been reactivated and will continue automatically",
            "renew_date": subscriber.subscription_renew_date,
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error reactivating subscription: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to reactivate subscription: {str(e)}"
        )


@router.post("/update-payment-method")
async def create_payment_update_session(
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a Stripe Billing Portal session for updating payment method.

    Users will be redirected to Stripe's secure portal to update their card.
    """
    # Only main accounts can update payment methods
    if current_user.parent_user_id:
        raise HTTPException(
            status_code=403,
            detail="Only the main account owner can update payment methods",
        )

    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=404, detail="No Stripe customer found. Please subscribe first."
        )

    try:
        # Create a billing portal session
        portal_session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=f"{FRONTEND_URL}/subscription/settings",
        )

        return {"portal_url": portal_session.url}

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating portal session: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create billing portal session: {str(e)}"
        )


@router.get("/wallet")
def get_wallet_info(
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user's wallet information including credits and spending history."""
    # Get effective user ID (main account for sub-users)
    effective_user_id = get_effective_user_id(current_user)

    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.user_id == effective_user_id)
        .first()
    )

    if not subscriber:
        # No subscriber record: treat as free wallet with zero credits/spending
        return {
            "current_credits": 0,
            "total_spending": 0,
            "subscription": "Free plan",
            "subscription_renew_date": None,
            "unlocked_leads": 0,
            "subscription_status": "inactive",
        }

    # Get subscription details
    subscription = None
    if subscriber.subscription_id:
        subscription = (
            db.query(models.user.Subscription)
            .filter(models.user.Subscription.id == subscriber.subscription_id)
            .first()
        )

    # Get unlocked leads with spending details (for effective user)
    unlocked_leads = (
        db.query(models.user.UnlockedLead)
        .filter(models.user.UnlockedLead.user_id == effective_user_id)
        .order_by(models.user.UnlockedLead.unlocked_at.desc())
        .limit(50)
        .all()
    )

    # Provide both a numeric count of unlocked leads and the detailed spending history
    unlocked_leads_count = len(unlocked_leads)
    spending_history = [
        {
            "job_id": lead.job_id,
            "credits_spent": lead.credits_spent,
            "unlocked_at": lead.unlocked_at,
        }
        for lead in unlocked_leads
    ]

    # Determine subscription name: prefer actual subscription, otherwise
    # if user has never received credits and spent nothing, show "Free".
    current_credits = subscriber.current_credits or 0
    total_spending = subscriber.total_spending or 0
    if subscription:
        subscription_name = subscription.name
    else:
        subscription_name = (
            "Free plan" if (current_credits == 0 and total_spending == 0) else None
        )

    return {
        "current_credits": current_credits,
        "total_spending": total_spending,
        "subscription": subscription_name,
        "subscription_renew_date": subscriber.subscription_renew_date,
        "unlocked_leads": unlocked_leads_count,
        "spending_history": spending_history,
        "subscription_status": subscriber.subscription_status,
        "is_sub_user": current_user.parent_user_id is not None,
    }
