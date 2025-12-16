import csv
import io
import json
import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional

import stripe
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from src.app import models, schemas
from src.app.api.deps import get_current_user
from fastapi import Security
from src.app.schemas.subscription import UpdateTierPricingRequest

# Admin-only dependency (replace with your actual admin check)
def admin_required(current_user=Depends(get_current_user)):
    if not getattr(current_user, "role", None) == "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return current_user

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


@router.get("/plans", response_model=List[schemas.subscription.StandardPlanResponse])
def get_subscription_plans(db: Session = Depends(get_db)):
    """Get all available subscription plans (Starter, Pro, Enterprise only), including Stripe IDs."""
    subscriptions = (
        db.query(models.user.Subscription)
        .filter(models.user.Subscription.name.in_(["Starter", "Pro", "Enterprise"]))
        .all()
    )
    # Ensure stripe_price_id and stripe_product_id are included in the response
    return [
        schemas.subscription.StandardPlanResponse(
            id=s.id,
            name=s.name,
            price=s.price,
            credits=s.credits,
            max_seats=s.max_seats,
            stripe_price_id=s.stripe_price_id,
            stripe_product_id=s.stripe_product_id,
        )
        for s in subscriptions
    ]


@router.post(
    "/calculate-custom-plan",
    response_model=schemas.subscription.CalculateCustomPlanResponse,
)
def calculate_custom_plan(
    data: schemas.subscription.CalculateCustomPlanRequest,
    db: Session = Depends(get_db),
):
    """
    Calculate the total price for a custom plan based on number of credits and seats.

    Uses the pricing set by admin in the Custom tier:
    - credit_price: Price per credit
    - seat_price: Price per seat

    Creates a unique Stripe product and price for this custom configuration.
    Returns breakdown of costs, total price, and Stripe IDs for checkout.
    """
    # Get Custom tier pricing
    custom_tier = (
        db.query(models.user.Subscription)
        .filter(models.user.Subscription.name == "Custom")
        .first()
    )

    if not custom_tier:
        raise HTTPException(
            status_code=404,
            detail="Custom tier not found. Please contact administrator.",
        )

    if not custom_tier.credit_price or not custom_tier.seat_price:
        raise HTTPException(
            status_code=400,
            detail="Custom tier pricing not configured. Please contact administrator.",
        )

    # Convert string prices to float for calculation
    try:
        credit_price = float(custom_tier.credit_price)
        seat_price = float(custom_tier.seat_price)
    except ValueError:
        raise HTTPException(
            status_code=500,
            detail="Invalid pricing configuration. Please contact administrator.",
        )

    # Calculate costs
    total_credits_cost = data.credits * credit_price
    total_seats_cost = data.seats * seat_price
    total_price = total_credits_cost + total_seats_cost
    total_price_in_cents = int(total_price * 100)

    # Create Stripe product and price for this custom configuration
    try:
        # Create a unique product for this custom plan
        product = stripe.Product.create(
            name=f"Custom Plan - {data.credits} Credits, {data.seats} Seats",
            description=f"{data.credits} credits @ ${custom_tier.credit_price} each + {data.seats} seats @ ${custom_tier.seat_price} each",
        )

        # Create a recurring price for this custom configuration
        price = stripe.Price.create(
            product=product.id,
            unit_amount=total_price_in_cents,
            currency="usd",
            recurring={"interval": "month"},
        )

        logger.info(
            f"Created Stripe custom product {product.id} and price {price.id} for ${total_price:.2f}/month"
        )

        return {
            "credits": data.credits,
            "seats": data.seats,
            "credit_price": custom_tier.credit_price,
            "seat_price": custom_tier.seat_price,
            "total_credits_cost": f"{total_credits_cost:.2f}",
            "total_seats_cost": f"{total_seats_cost:.2f}",
            "total_price": f"{total_price:.2f}",
            "stripe_price_id": price.id,
            "stripe_product_id": product.id,
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating custom plan: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create Stripe price: {str(e)}"
        )


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
    Create a Stripe Checkout session for subscription.
    Requires a valid Stripe price ID (for both standard and custom plans).
    """
    # Only main accounts can subscribe (sub-users share main account's subscription)
    if current_user.parent_user_id:
        raise HTTPException(
            status_code=403,
            detail="Sub-users cannot create subscriptions. The main account owner manages subscriptions.",
        )

    # Require and validate stripe_price_id
    if not data.stripe_price_id or not data.stripe_price_id.startswith("price_"):
        raise HTTPException(
            status_code=400,
            detail="stripe_price_id is required and must start with 'price_'",
        )

    # Verify the price exists in Stripe
    try:
        stripe_price = stripe.Price.retrieve(data.stripe_price_id)
        if not stripe_price.active:
            raise HTTPException(
                status_code=400, detail="The specified Stripe price is not active"
            )
    except stripe.error.InvalidRequestError:
        raise HTTPException(
            status_code=400, detail="The specified Stripe price does not exist"
        )
    except stripe.error.StripeError as e:
        logger.error(
            f"Stripe error validating price {data.stripe_price_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=500, detail="Failed to validate Stripe price"
        )

    stripe_price_id = data.stripe_price_id

    # Create or retrieve Stripe customer
    if not current_user.stripe_customer_id:
        customer = stripe.Customer.create(
            email=current_user.email,
            metadata={"user_id": str(current_user.id)},
        )
        current_user.stripe_customer_id = customer.id
        db.commit()
        logger.info(f"Created Stripe customer {customer.id} for user {current_user.email}")
    else:
        customer = stripe.Customer.retrieve(current_user.stripe_customer_id)
        logger.info(f"Using existing Stripe customer {customer.id}")

    # Create Stripe Checkout session
    # For existing Stripe price id, prepare metadata and allow the shared
    # checkout-creation logic below to create the session (covers both
    # existing-price and personalized plan flows).
    metadata = {
        "user_id": current_user.id,
        "subscription_plan_id": stripe_price_id,
        "subscription_plan_name": None,
        "user_email": current_user.email,
        "stripe_price_id": stripe_price_id,
    }

    if data.name and data.credits and data.price and data.seats:
        # Create personalized checkout
        price_str = data.price.replace("$", "").replace("/month", "").strip()
        price_in_cents = int(float(price_str) * 100)

        # Create unique product for this checkout
        product = stripe.Product.create(
            name=f"{data.name} Plan - {current_user.email}",
            description=f"{data.credits} credits per month, {data.seats} seats - {current_user.email}",
        )

        # Create price for this product
        price = stripe.Price.create(
            product=product.id,
            unit_amount=price_in_cents,
            currency="usd",
            recurring={"interval": "month"},
        )

        logger.info(
            f"Created personalized Stripe product {product.id} and price {price.id} for {current_user.email}"
        )

        stripe_price_id = price.id
        metadata = {
            "user_id": current_user.id,
            "subscription_plan_name": data.name,
            "credits": data.credits,
            "seats": data.seats,
            "price": data.price,
            "user_email": current_user.email,
            "stripe_price_id": price.id,
            "stripe_product_id": product.id,
        }

    else:
        raise HTTPException(
            status_code=400,
            detail="Either provide stripe_price_id for existing price, or provide name, credits, price, seats for personalized checkout",
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
                    "price": stripe_price_id,
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url=f"{FRONTEND_URL}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/subscription/cancel",
            metadata=metadata,
            subscription_data={
                "metadata": {
                    "user_id": current_user.id,
                    "subscription_plan_name": metadata.get(
                        "subscription_plan_name", "Custom"
                    ),
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
    stripe_subscription_id = session["subscription"]

    # Get user
    user = db.query(models.user.User).filter(models.user.User.id == user_id).first()
    if not user:
        logger.error(f"User not found for session {session['id']}")
        return

    # Check if this is a personalized checkout (has credits in metadata)
    if "credits" in session["metadata"]:
        # Personalized plan - create or find subscription based on details
        plan_name = session["metadata"]["subscription_plan_name"]
        credits = int(session["metadata"]["credits"])
        seats = int(session["metadata"]["seats"])
        price = session["metadata"]["price"]

        # Try to find existing subscription with matching details
        subscription_plan = (
            db.query(models.user.Subscription)
            .filter(
                models.user.Subscription.name == plan_name,
                models.user.Subscription.credits == credits,
                models.user.Subscription.max_seats == seats,
                models.user.Subscription.price == price,
            )
            .first()
        )

        if not subscription_plan:
            # Create a new subscription entry for this personalized plan
            subscription_plan = models.user.Subscription(
                name=plan_name,
                price=price,
                credits=credits,
                max_seats=seats,
            )
            db.add(subscription_plan)
            db.flush()  # Get the ID
            logger.info(
                f"Created personalized subscription plan: {plan_name} for user {user.email}"
            )
    else:
        # Standard checkout - use subscription_plan_id
        subscription_plan_id = session["metadata"].get("subscription_plan_id")
        if subscription_plan_id and subscription_plan_id != "custom":
            subscription_plan = (
                db.query(models.user.Subscription)
                .filter(models.user.Subscription.id == int(subscription_plan_id))
                .first()
            )
        else:
            # Fallback for custom plans
            subscription_plan = (
                db.query(models.user.Subscription)
                .filter(models.user.Subscription.name == "Custom")
                .first()
            )

    if not subscription_plan:
        logger.error(f"Subscription plan not found for session {session['id']}")
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
            subscription_id=subscription_plan.id,
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
        subscriber.subscription_id = subscription_plan.id
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


@router.put("/admin/update-all-tiers-pricing")
def update_all_tiers_pricing(
    data: schemas.subscription.UpdateAllTiersPricingRequest,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Admin endpoint to update subscription tiers pricing (Starter, Professional, Enterprise, Custom).

    Updates multiple tiers at once. Provide an array of tier updates.
    - Standard tiers (Starter, Professional, Enterprise): monthly_price, credits, seats
    - Custom tier: credit_price, seat_price

    Only admin users can access this endpoint.
    """
    # Check if user is admin
    if current_user.email != "admin@tigerleads.com":
        raise HTTPException(
            status_code=403,
            detail="Only administrators can update subscription pricing",
        )

    if not data.tiers:
        raise HTTPException(status_code=400, detail="No tiers provided for update")

    updated_tiers = []
    errors = []

    # Process each tier update
    for tier_data in data.tiers:
        try:
            # Validate tier_name is provided
            if not tier_data.tier_name:
                errors.append(
                    {
                        "tier_name": None,
                        "error": "tier_name is required for each tier update",
                    }
                )
                continue

            # Find the subscription tier by name
            subscription = (
                db.query(models.user.Subscription)
                .filter(models.user.Subscription.name == tier_data.tier_name)
                .first()
            )

            if not subscription:
                errors.append(
                    {
                        "tier_name": tier_data.tier_name,
                        "error": f"Subscription tier '{tier_data.tier_name}' not found",
                    }
                )
                continue

            # Update fields based on tier type
            if tier_data.tier_name.lower() == "custom":
                # For Custom tier, update credit_price and seat_price
                if tier_data.credit_price is not None:
                    subscription.credit_price = tier_data.credit_price

                if tier_data.seat_price is not None:
                    subscription.seat_price = tier_data.seat_price

                tier_response = {
                    "id": subscription.id,
                    "name": subscription.name,
                    "credit_price": subscription.credit_price,
                    "seat_price": subscription.seat_price,
                }
            else:
                # For standard tiers, update monthly_price, credits, seats
                price_updated = False

                if tier_data.monthly_price is not None:
                    subscription.price = tier_data.monthly_price
                    price_updated = True

                if tier_data.credits is not None:
                    subscription.credits = tier_data.credits

                if tier_data.seats is not None:
                    subscription.max_seats = tier_data.seats

                # If price changed, create new Stripe price
                if price_updated and tier_data.monthly_price:
                    try:
                        # Convert price string to cents (Stripe uses cents)
                        # Remove $ and /month, convert to float, then to cents
                        price_str = (
                            tier_data.monthly_price.replace("$", "")
                            .replace("/month", "")
                            .strip()
                        )
                        price_in_cents = int(float(price_str) * 100)

                        # Create or update Stripe product
                        if not subscription.stripe_product_id:
                            # Create new product
                            product = stripe.Product.create(
                                name=f"{tier_data.tier_name} Plan",
                                description=f"{tier_data.credits} credits, {tier_data.seats} seats",
                            )
                            subscription.stripe_product_id = product.id
                            logger.info(
                                f"Created Stripe product {product.id} for {tier_data.tier_name}"
                            )
                        else:
                            # Update existing product description
                            stripe.Product.modify(
                                subscription.stripe_product_id,
                                description=f"{tier_data.credits} credits, {tier_data.seats} seats",
                            )

                        # Create new price (Stripe doesn't allow modifying prices)
                        new_price = stripe.Price.create(
                            product=subscription.stripe_product_id,
                            unit_amount=price_in_cents,
                            currency="usd",
                            recurring={"interval": "month"},
                        )

                        # Archive old price if exists
                        if subscription.stripe_price_id:
                            try:
                                stripe.Price.modify(
                                    subscription.stripe_price_id, active=False
                                )
                                logger.info(
                                    f"Archived old Stripe price {subscription.stripe_price_id}"
                                )
                            except Exception as e:
                                logger.warning(f"Could not archive old price: {e}")

                        # Update with new price ID
                        subscription.stripe_price_id = new_price.id
                        logger.info(
                            f"Created new Stripe price {new_price.id} for {tier_data.tier_name}: ${price_str}/month"
                        )

                    except Exception as stripe_error:
                        logger.error(
                            f"Stripe error for {tier_data.tier_name}: {stripe_error}"
                        )
                        errors.append(
                            {
                                "tier_name": tier_data.tier_name,
                                "error": f"Database updated but Stripe sync failed: {str(stripe_error)}",
                            }
                        )

                tier_response = {
                    "id": subscription.id,
                    "name": subscription.name,
                    "monthly_price": subscription.price,
                    "credits": subscription.credits,
                    "seats": subscription.max_seats,
                    "stripe_price_id": subscription.stripe_price_id,
                    "stripe_product_id": subscription.stripe_product_id,
                }

            updated_tiers.append(tier_response)

        except Exception as e:
            errors.append({"tier_name": tier_data.tier_name, "error": str(e)})

    # Commit all changes if no errors
    if errors:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Some tiers failed to update",
                "errors": errors,
                "updated_tiers": updated_tiers,
            },
        )

    try:
        db.commit()

        return {
            "message": f"Successfully updated {len(updated_tiers)} tier(s)",
            "tiers": updated_tiers,
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error committing tier pricing updates: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update tier pricing: {str(e)}"
        )
