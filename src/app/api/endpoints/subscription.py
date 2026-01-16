import csv
import io
import json
import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional

import stripe
from dotenv import load_dotenv
from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    Security,
    status,
)
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session, joinedload

from src.app import models, schemas
from src.app.api.deps import (
    get_current_user,
    get_effective_user,
    require_admin,
    require_admin_token,
    require_main_account,
)
from src.app.schemas.subscription import UpdateTierPricingRequest


# Admin-only dependency (replace with your actual admin check)
def admin_required(current_user=Depends(get_current_user)):
    if not getattr(current_user, "role", None) == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required."
        )
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
def get_subscription_plans(
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all available subscription plans (Starter, Pro, Enterprise only), including Stripe IDs."""
    subscriptions = (
        db.query(models.user.Subscription)
        .filter(
            models.user.Subscription.name.in_(["Starter", "Professional", "Enterprise"])
        )
        .all()
    )

    # Static lead access descriptions per tier (kept hard-coded as requested)
    # Use name-inspection to handle variants like 'Pro' vs 'Professional'.
    def lead_access_for_name(name: str) -> str:
        n = (name or "").lower()
        if "starter" in n or "tier 1" in n:
            return "Upto 40% of all available leads"
        if "professional" in n or "tier 2" in n:
            return "Upto 75% of all available leads"
        if "enterprise" in n or "tier 3" in n or "elite" in n:
            return "100% of all available leads"
        return ""

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
            lead_access=lead_access_for_name(s.name),
        )
        for s in subscriptions
    ]


@router.post(
    "/calculate-custom-plan",
    response_model=schemas.subscription.CalculateCustomPlanResponse,
)
def calculate_custom_plan(
    data: schemas.subscription.CalculateCustomPlanRequest,
    current_user: models.user.User = Depends(require_main_account),
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
        # Persist this custom plan in the subscriptions table so it can be
        # referenced later (store stripe ids and calculated price).
        try:
            existing = (
                db.query(models.user.Subscription)
                .filter(models.user.Subscription.stripe_price_id == price.id)
                .first()
            )

            plan_name = f"Custom - {data.credits} credits, {data.seats} seats"
            price_str = f"{total_price:.2f}"

            if not existing:
                plan = models.user.Subscription(
                    name=plan_name,
                    price=price_str,
                    credits=int(data.credits),
                    max_seats=int(data.seats),
                    stripe_price_id=price.id,
                    stripe_product_id=product.id,
                    credit_price=custom_tier.credit_price,
                    seat_price=custom_tier.seat_price,
                )
                db.add(plan)
                db.commit()
                db.refresh(plan)
                logger.info(
                    f"Persisted custom subscription plan id={plan.id} stripe_price_id={price.id}"
                )
            else:
                existing.name = plan_name
                existing.price = price_str
                existing.credits = int(data.credits)
                existing.max_seats = int(data.seats)
                existing.stripe_product_id = product.id
                existing.credit_price = custom_tier.credit_price
                existing.seat_price = custom_tier.seat_price
                db.commit()
                logger.info(
                    f"Updated existing subscription plan id={existing.id} for stripe_price_id={price.id}"
                )
        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
            logger.exception("Failed to persist custom subscription plan: %s", e)

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
    current_user: models.user.User = Depends(require_main_account),
    db: Session = Depends(get_db),
):
    """
    Create a Stripe Checkout session for subscription.
    Requires a valid Stripe price ID (for both standard and custom plans).
    """
    # `require_main_account` dependency ensures only main account owners can create checkout sessions

    # Validate input: either provide existing `stripe_price_id` OR provide
    # all custom fields (`name`, `credits`, `price`, `seats`). Return a
    # clear error message listing which fields are missing when applicable.
    stripe_price_id = None
    if data.stripe_price_id:
        if not data.stripe_price_id.startswith("price_"):
            raise HTTPException(
                status_code=400,
                detail="Provided stripe_price_id must start with 'price_'",
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
    else:
        # Check custom/personalized plan fields
        missing = []
        if not data.name:
            missing.append("name")
        if data.credits is None:
            missing.append("credits")
        if not data.price:
            missing.append("price")
        if data.seats is None:
            missing.append("seats")

        if missing:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Missing required fields for personalized checkout",
                    "missing_fields": missing,
                    "note": "Provide either 'stripe_price_id' or all of ['name','credits','price','seats']",
                },
            )

    # Stripe customer will be created/retrieved in the guarded try/except
    # below to ensure Stripe errors are handled in one place. We persist
    # `current_user.stripe_customer_id` there so we don't create duplicate
    # customers across multiple code paths.

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
        "auto_renew": str(data.auto_renew),  # Pass auto-renew preference
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
            "auto_renew": str(data.auto_renew),  # Pass auto-renew preference
        }

    elif stripe_price_id:
        # Using an existing Stripe price id provided in the request.
        # `metadata` was initialized above to include `stripe_price_id`.
        pass

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
            success_url=f"{FRONTEND_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/payment/failure",
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
    - invoice.payment_action_required: Payment requires authentication (3D Secure)
    - invoice.upcoming: Invoice about to be charged (for reminders)
    - customer.subscription.deleted: Subscription canceled
    - customer.subscription.updated: Subscription status/plan changed
    - customer.subscription.paused: Subscription paused
    - customer.subscription.resumed: Subscription resumed from pause
    """
    # Read raw payload for verification and debugging
    payload = await request.body()

    # Temporary debug logging: record headers, signature and a truncated payload
    try:
        headers_dict = dict(request.headers)
    except Exception:
        headers_dict = {}

    logger.info(
        "Incoming webhook: headers_keys=%s stripe_signature=%s payload_len=%d",
        list(headers_dict.keys()),
        stripe_signature,
        len(payload),
    )

    # Log a truncated UTF-8 preview of the payload (avoid huge logs)
    try:
        payload_preview = payload.decode("utf-8")[:2000]
        logger.debug("Webhook payload preview: %s", payload_preview)
    except Exception:
        logger.debug("Webhook payload preview: <binary or undecodable>")

    try:
        # Debug: ensure the stripe package's apps attribute is present
        try:
            logger.info(
                "stripe.__version__=%s stripe.apps=%s",
                getattr(stripe, "__version__", None),
                type(getattr(stripe, "apps", None)),
            )
        except Exception:
            logger.info("Failed to introspect stripe package")

        event = stripe.Webhook.construct_event(
            payload, stripe_signature, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        logger.error(f"Invalid payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    logger.info(
        f"Received Stripe webhook event: {event.get('type')} id={event.get('id')}"
    )

    # Handle different event types inside a safe try/except so we log full stacktraces
    try:
        if event["type"] == "checkout.session.completed":
            await handle_checkout_session_completed(event["data"]["object"], db)

        elif event["type"] == "invoice.payment_succeeded":
            await handle_invoice_payment_succeeded(event["data"]["object"], db)

        elif event["type"] == "invoice.payment_failed":
            await handle_invoice_payment_failed(event["data"]["object"], db)

        elif event["type"] == "invoice.payment_action_required":
            await handle_invoice_payment_action_required(event["data"]["object"], db)

        elif event["type"] == "invoice.upcoming":
            await handle_invoice_upcoming(event["data"]["object"], db)

        elif event["type"] == "customer.subscription.deleted":
            await handle_subscription_deleted(event["data"]["object"], db)

        elif event["type"] == "customer.subscription.updated":
            await handle_subscription_updated(event["data"]["object"], db)

        elif event["type"] == "customer.subscription.paused":
            await handle_subscription_paused(event["data"]["object"], db)

        elif event["type"] == "customer.subscription.resumed":
            await handle_subscription_resumed(event["data"]["object"], db)

        else:
            # Log unhandled events for monitoring (don't fail)
            logger.info(f"Unhandled webhook event type: {event.get('type')}")

        return {"status": "success"}

    except Exception as e:
        # Log full stacktrace and event context for diagnosis
        logger.exception(
            "Unhandled exception while processing webhook event id=%s type=%s: %s",
            event.get("id"),
            event.get("type"),
            str(e),
        )

        # Also include a short payload preview for easier debugging
        try:
            payload_preview = event.get("data", {}).get("object", {})
            logger.debug(
                "Webhook event object preview: %s", str(payload_preview)[:2000]
            )
        except Exception:
            pass

        # Return 500 so Stripe will retry; the logs will show the exception details
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error while processing webhook. Check server logs for full trace.",
                "event_id": event.get("id"),
                "event_type": event.get("type"),
            },
        )


async def handle_checkout_session_completed(session, db: Session):
    """Handle successful checkout (first-time subscription)."""
    logger.info(f"Processing checkout.session.completed for session {session['id']}")

    # Debug logs to inspect incoming session payload
    logger.debug(f"Session keys: {list(session.keys())}")
    logger.debug(f"Session subscription: {session.get('subscription')}")
    logger.debug(f"Session customer: {session.get('customer')}")
    logger.debug(f"Session metadata: {session.get('metadata')}")

    try:
        # Safely extract metadata and fields
        metadata = session.get("metadata") or {}

        try:
            user_id = (
                int(metadata.get("user_id"))
                if metadata.get("user_id") is not None
                else None
            )
        except (ValueError, TypeError) as e:
            logger.error(
                f"Invalid user_id in metadata for session {session.get('id')}: {metadata.get('user_id')}"
            )
            raise ValueError(f"Invalid user_id in metadata: {e}")

        if not user_id:
            logger.error(
                f"No user_id found in metadata for session {session.get('id')}"
            )
            raise ValueError("user_id is required in checkout session metadata")

        stripe_subscription_id = session.get("subscription")

        if not stripe_subscription_id:
            logger.error(
                f"No subscription ID in session - will be handled by invoice events for session {session.get('id')}"
            )
            return  # Not an error, just skip this handler

        # Get user
        user = db.query(models.user.User).filter(models.user.User.id == user_id).first()
        if not user:
            logger.error(
                f"User not found for user_id {user_id} in session {session.get('id')}"
            )
            raise ValueError(f"User {user_id} not found in database")

        subscription_plan = None

        # Check if this is a personalized checkout (has credits in metadata)
        if "credits" in metadata:
            # Personalized plan - create or find subscription based on details
            plan_name = metadata.get("subscription_plan_name")
            try:
                credits = int(metadata.get("credits", 0))
                seats = int(metadata.get("seats", 0))
            except (ValueError, TypeError) as e:
                logger.error(
                    f"Invalid credits/seats in metadata for session {session.get('id')}: {e}"
                )
                raise ValueError(f"Invalid credits or seats in metadata: {e}")

            price = metadata.get("price")

            # Validate required fields
            if not plan_name or not price or credits <= 0 or seats <= 0:
                logger.error(
                    f"Invalid personalized plan metadata for session {session.get('id')}: "
                    f"plan_name={plan_name}, price={price}, credits={credits}, seats={seats}"
                )
                raise ValueError(
                    "Invalid personalized plan metadata: missing or invalid fields"
                )

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
                    stripe_price_id=metadata.get("stripe_price_id"),
                    stripe_product_id=metadata.get("stripe_product_id"),
                )
                db.add(subscription_plan)
                db.flush()  # Get the ID
                logger.info(
                    f"Created personalized subscription plan: {plan_name} for user {user.email}"
                )
        else:
            # Standard checkout - lookup by stripe_price_id (NOT database ID!)
            stripe_price_id = metadata.get("stripe_price_id") or metadata.get(
                "subscription_plan_id"
            )

            if stripe_price_id and stripe_price_id.startswith("price_"):
                # Look up by Stripe price ID
                subscription_plan = (
                    db.query(models.user.Subscription)
                    .filter(models.user.Subscription.stripe_price_id == stripe_price_id)
                    .first()
                )

                if not subscription_plan:
                    logger.warning(
                        f"Subscription plan not found for stripe_price_id {stripe_price_id} in session {session.get('id')}. "
                        "Trying fallback to Custom plan."
                    )

            # Fallback: try Custom plan if no match found
            if not subscription_plan:
                subscription_plan = (
                    db.query(models.user.Subscription)
                    .filter(models.user.Subscription.name == "Custom")
                    .first()
                )

        if not subscription_plan:
            error_msg = (
                f"Subscription plan not found for session {session.get('id')}. "
                f"Metadata: stripe_price_id={metadata.get('stripe_price_id')}, "
                f"subscription_plan_id={metadata.get('subscription_plan_id')}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Get or create subscriber record
        subscriber = (
            db.query(models.user.Subscriber)
            .filter(models.user.Subscriber.user_id == user_id)
            .first()
        )

        # Get auto_renew preference from metadata
        auto_renew = metadata.get("auto_renew", "true").lower() == "true"
        
        if not subscriber:
            subscriber = models.user.Subscriber(
                user_id=user_id,
                subscription_id=subscription_plan.id,
                current_credits=subscription_plan.credits or 0,
                seats_used=0,
                purchased_seats=0,  # New subscription starts with 0 bonus seats
                subscription_start_date=datetime.utcnow(),
                subscription_renew_date=datetime.utcnow() + timedelta(days=30),
                is_active=True,
                stripe_subscription_id=stripe_subscription_id,
                subscription_status="active",
                auto_renew=auto_renew,  # Set user's preference
            )
            db.add(subscriber)
            
            # If user opted out of auto-renew during checkout, schedule cancellation
            if not auto_renew:
                try:
                    stripe.Subscription.modify(
                        stripe_subscription_id,
                        cancel_at_period_end=True
                    )
                    logger.info(f"User {user.email} opted out of auto-renew during checkout. Subscription will cancel at period end.")
                except stripe.error.StripeError as e:
                    logger.error(f"Failed to set cancel_at_period_end for subscription {stripe_subscription_id}: {e}")
            logger.info(
                f"Created new subscriber record for user {user.email} with plan {subscription_plan.name}"
            )
        else:
            # Update existing subscriber (switching plans)
            old_subscription_id = subscriber.subscription_id
            old_stripe_subscription_id = subscriber.stripe_subscription_id
            old_credits = subscriber.current_credits  # Preserve existing credits
            
            # Get old plan to add its seats to purchased_seats
            old_plan_seats = 0
            if old_subscription_id:
                old_plan = (
                    db.query(models.user.Subscription)
                    .filter(models.user.Subscription.id == old_subscription_id)
                    .first()
                )
                if old_plan:
                    old_plan_seats = old_plan.max_seats or 0
            
            # Cancel the old Stripe subscription to avoid double billing
            if old_stripe_subscription_id and old_stripe_subscription_id != stripe_subscription_id:
                try:
                    # Cancel the old subscription immediately (not at period end)
                    # since user is switching to a new subscription
                    stripe.Subscription.delete(old_stripe_subscription_id)
                    logger.info(
                        f"Canceled old Stripe subscription {old_stripe_subscription_id} for user {user.email}"
                    )
                except stripe.error.InvalidRequestError as e:
                    # Subscription might already be canceled or doesn't exist
                    logger.warning(
                        f"Could not cancel old Stripe subscription {old_stripe_subscription_id}: {str(e)}"
                    )
                except stripe.error.StripeError as e:
                    # Log error but don't fail the webhook - the new subscription is valid
                    logger.error(
                        f"Stripe error canceling old subscription {old_stripe_subscription_id}: {str(e)}"
                    )
            
            subscriber.subscription_id = subscription_plan.id
            # ADD new subscription credits to existing credits
            new_credits_from_plan = subscription_plan.credits or 0
            subscriber.current_credits = old_credits + new_credits_from_plan
            # ADD old plan's seats to purchased_seats (accumulate like credits)
            subscriber.purchased_seats = (subscriber.purchased_seats or 0) + old_plan_seats
            subscriber.subscription_start_date = datetime.utcnow()
            subscriber.subscription_renew_date = datetime.utcnow() + timedelta(days=30)
            subscriber.is_active = True
            subscriber.stripe_subscription_id = stripe_subscription_id
            subscriber.subscription_status = "active"
            subscriber.auto_renew = auto_renew  # Update auto-renew preference
            
            # If user opted out during plan switch, schedule cancellation
            if not auto_renew:
                try:
                    stripe.Subscription.modify(
                        stripe_subscription_id,
                        cancel_at_period_end=True
                    )
                    logger.info(f"User {user.email} opted out of auto-renew during plan switch.")
                except stripe.error.StripeError as e:
                    logger.error(f"Failed to set cancel_at_period_end: {e}")
            
            logger.info(
                f"Updated existing subscriber record for user {user.email} with plan {subscription_plan.name}. "
                f"Previous credits: {old_credits}, New plan credits: {new_credits_from_plan}, Total credits: {subscriber.current_credits}. "
                f"Previous plan seats: {old_plan_seats}, Purchased seats: {subscriber.purchased_seats}. "
                f"Old subscription_id: {old_subscription_id}, New subscription_id: {subscription_plan.id}, "
                f"Old Stripe subscription: {old_stripe_subscription_id}, New Stripe subscription: {stripe_subscription_id}"
            )

        # Commit all changes
        db.commit()

        # Auto-grant add-ons based on subscription tier
        try:
            # Refresh subscription_plan to ensure we have latest data
            db.refresh(subscription_plan)
            
            tier_level = getattr(subscription_plan, 'tier_level', None)
            has_stay_active = getattr(subscription_plan, 'has_stay_active_bonus', False)
            has_bonus = getattr(subscription_plan, 'has_bonus_credits', False)
            has_boost = getattr(subscription_plan, 'has_boost_pack', False)
            
            logger.info(
                f"Checking add-ons for subscription_plan {subscription_plan.name} (ID: {subscription_plan.id}): "
                f"tier_level={tier_level}, has_stay_active={has_stay_active}, "
                f"has_bonus={has_bonus}, has_boost={has_boost}"
            )
            
            # Normalize plan name for comparison
            plan_name_lower = subscription_plan.name.lower().strip()
            
            # Determine if this is a custom subscription (anything except Starter, Professional, Enterprise)
            is_custom = plan_name_lower not in ["starter", "professional", "enterprise"]
            
            if is_custom:
                logger.info(f"Subscription plan '{subscription_plan.name}' is Custom tier (not Starter/Professional/Enterprise)")
            
            logger.info(f"Auto-granting add-ons for {subscription_plan.name} to user {user.email}")
            
            # Tier 1 (Starter): Stay Active only
            if plan_name_lower == "starter":
                subscriber.stay_active_credits = 30
                logger.info(f"✓ Starter: Granted Stay Active Bonus (30 credits) to user {user.email}")
            
            # Tier 2 (Professional): Stay Active + Bonus Credits
            elif plan_name_lower == "professional":
                subscriber.stay_active_credits = 30
                subscriber.bonus_credits = 50
                logger.info(f"✓ Professional: Granted Stay Active Bonus (30 credits) + Bonus Credits (50 credits) to user {user.email}")
            
            # Tier 3 (Enterprise) OR Custom: Stay Active + Bonus Credits + Boost Pack
            elif plan_name_lower == "enterprise" or is_custom:
                subscriber.stay_active_credits = 30
                subscriber.bonus_credits = 50
                subscriber.boost_pack_credits = 100
                subscriber.boost_pack_seats = 1
                logger.info(f"✓ {'Custom (' + subscription_plan.name + ')' if is_custom else 'Enterprise'}: Granted all add-ons (Stay Active 30 + Bonus 50 + Boost Pack 100+1 seat) to user {user.email}")
            
            # Commit add-ons for ALL tiers
            db.commit()
            logger.info(f"✅ Successfully auto-granted all eligible add-ons for user {user.email}")
        except Exception as e:
            logger.exception(f"❌ Error auto-granting add-ons for user {user.email}: {e}")
            # Don't fail the entire webhook if add-on granting fails
            try:
                db.rollback()
                # Recommit the main subscription changes
                db.add(subscriber)
                db.commit()
            except Exception:
                pass

        # Try to record payment in payments table. Use amount from session if present,
        # otherwise fall back to subscription_plan.price when possible.
        try:
            # Determine amount (prefer cents fields from session)
            amount = None
            # Stripe checkout session often contains amount_total in cents
            amt_cents = session.get("amount_total") or session.get("amount_subtotal")
            if amt_cents:
                try:
                    amount = float(amt_cents) / 100.0
                except Exception:
                    amount = None

            # Fallback: price stored on subscription_plan (may be string)
            if (
                amount is None
                and subscription_plan
                and getattr(subscription_plan, "price", None)
            ):
                try:
                    amount = float(subscription_plan.price)
                except Exception:
                    amount = None

            if amount is not None:
                try:
                    # Prepare payment metadata
                    stripe_session_id = session.get("id")
                    stripe_invoice_id = None
                    currency = session.get("currency") or metadata.get("currency")
                    subscriber_id = subscriber.id if subscriber else None
                    subscription_id = (
                        subscription_plan.id if subscription_plan else None
                    )

                    logger.info(
                        "Attempting to record checkout payment: subscription_id=%s subscriber_id=%s session_id=%s amt_cents=%s amount=%s currency=%s",
                        subscription_id,
                        subscriber_id,
                        stripe_session_id,
                        amt_cents,
                        amount,
                        currency,
                    )

                    # Insert minimal payment record: subscriber_id, amount (USD), payment_date, created_at
                    # Check if payment already exists for this session to avoid duplicates
                    existing_payment = db.execute(
                        text(
                            "SELECT id FROM payments WHERE subscriber_id = :subscriber_id "
                            "AND amount = :amt AND payment_date = :pd"
                        ),
                        {
                            "subscriber_id": subscriber_id,
                            "amt": amount,
                            "pd": datetime.utcnow().date(),  # Check by date only
                        },
                    ).fetchone()
                    
                    if existing_payment:
                        logger.info(
                            f"Payment already recorded for subscriber {subscriber_id} on {datetime.utcnow().date()}"
                        )
                    else:
                        db.execute(
                            text(
                                "INSERT INTO payments (subscriber_id, amount, payment_date, created_at) "
                                "VALUES (:subscriber_id, :amt, :pd, now()) "
                                "ON CONFLICT DO NOTHING"
                            ),
                            {
                                "subscriber_id": subscriber_id,
                                "amt": amount,
                                "pd": datetime.utcnow(),
                            },
                        )
                        db.commit()
                        logger.info(
                            f"Recorded payment of {amount} for subscriber {subscriber_id}"
                        )
                except Exception:
                    logger.exception(
                        "Could not record payment in payments table for checkout session %s",
                        session.get("id"),
                    )
                    try:
                        db.rollback()
                    except Exception:
                        pass
        except Exception:
            # Don't let payment recording affect webhook processing
            logger.exception(
                "Unexpected error while attempting to record checkout payment"
            )

        logger.info(
            f"Successfully activated {subscription_plan.name} subscription for user {user.email}. "
            f"Credits: {subscription_plan.credits}, Max seats: {subscription_plan.max_seats}, "
            f"Subscriber ID: {subscriber.id}"
        )

        # TODO: Send welcome email to user

    except Exception as e:
        logger.exception(
            f"Error in handle_checkout_session_completed for session {session.get('id')}: {e}"
        )
        try:
            db.rollback()
        except Exception:
            pass
        # Re-raise the exception so webhook handler knows to retry
        raise


async def handle_invoice_payment_succeeded(invoice, db: Session):
    """Handle successful monthly renewal payment."""
    logger.info(f"Processing invoice.payment_succeeded for invoice {invoice.get('id')}")

    try:
        # Safely obtain subscription id (top-level or from invoice lines)
        stripe_subscription_id = invoice.get("subscription")

        if not stripe_subscription_id:
            lines = invoice.get("lines", {}).get("data", []) or []
            for line in lines:
                if not line:
                    continue
                # Some stripe payloads attach subscription to the line item
                if line.get("subscription"):
                    stripe_subscription_id = line.get("subscription")
                    break

        # Attempt to find the subscriber by several fallbacks. Prefer direct
        # stripe_subscription_id match when available, otherwise try invoice
        # metadata.user_id, invoice.customer -> user, or metadata.stripe_price_id.
        subscriber = None
        found_by = None
        if stripe_subscription_id:
            subscriber = (
                db.query(models.user.Subscriber)
                .filter(
                    models.user.Subscriber.stripe_subscription_id
                    == stripe_subscription_id
                )
                .first()
            )
            if subscriber:
                found_by = f"stripe_subscription_id={stripe_subscription_id}"

        # Fallbacks when subscriber isn't found by stripe_subscription_id:
        # 1) invoice.metadata.user_id -> find subscriber by user_id
        # 2) invoice.customer -> find User by stripe_customer_id then Subscriber by user_id
        # 3) invoice.metadata.stripe_price_id -> map to Subscription and create/update subscriber
        if not subscriber:
            # Try metadata user_id
            try:
                meta_user_id = invoice.get("metadata", {}).get("user_id")
                if meta_user_id:
                    try:
                        meta_user_id_int = int(meta_user_id)
                    except Exception:
                        meta_user_id_int = None
                    if meta_user_id_int:
                        subscriber = (
                            db.query(models.user.Subscriber)
                            .filter(models.user.Subscriber.user_id == meta_user_id_int)
                            .first()
                        )
                        if subscriber:
                            found_by = f"metadata.user_id={meta_user_id_int}"
            except Exception:
                subscriber = subscriber

        if not subscriber:
            # Try finding user by Stripe customer id
            try:
                customer_id = invoice.get("customer")
                if customer_id:
                    user = (
                        db.query(models.user.User)
                        .filter(models.user.User.stripe_customer_id == customer_id)
                        .first()
                    )
                    if user:
                        subscriber = (
                            db.query(models.user.Subscriber)
                            .filter(models.user.Subscriber.user_id == user.id)
                            .first()
                        )
                        if subscriber:
                            found_by = f"customer_id={customer_id} -> user_id={user.id}"
            except Exception:
                pass

        if not subscriber:
            # As a last resort, try to map by price in metadata and create a minimal subscriber record
            try:
                meta_price = invoice.get("metadata", {}).get("stripe_price_id")
                if meta_price:
                    subscription_plan = (
                        db.query(models.user.Subscription)
                        .filter(models.user.Subscription.stripe_price_id == meta_price)
                        .first()
                    )
                    # If we found a user from customer above, create subscriber record
                    user = None
                    customer_id = invoice.get("customer")
                    if customer_id:
                        user = (
                            db.query(models.user.User)
                            .filter(models.user.User.stripe_customer_id == customer_id)
                            .first()
                        )
                    if user:
                        subscriber = (
                            db.query(models.user.Subscriber)
                            .filter(models.user.Subscriber.user_id == user.id)
                            .first()
                        )
                        if not subscriber:
                            # create minimal subscriber
                            subscriber = models.user.Subscriber(
                                user_id=user.id,
                                subscription_id=(
                                    subscription_plan.id if subscription_plan else None
                                ),
                                current_credits=(
                                    subscription_plan.credits
                                    if subscription_plan
                                    else 0
                                ),
                                subscription_start_date=datetime.utcnow(),
                                subscription_renew_date=(
                                    datetime.utcnow() + timedelta(days=30)
                                ),
                                is_active=True,
                                stripe_subscription_id=stripe_subscription_id,
                                subscription_status="active",
                            )
                            db.add(subscriber)
                            # Don't commit here - commit once at the end with other updates
                            found_by = f"created_minimal_for_customer={customer_id}"
            except Exception:
                pass
        if not subscriber:
            logger.error(
                "Subscriber not found for invoice (no subscription mapping) invoice=%s metadata=%s customer=%s",
                invoice.get("id"),
                invoice.get("metadata"),
                invoice.get("customer"),
            )
            return

        logger.info(f"Found subscriber id={subscriber.id} via {found_by}")

        # Try to get associated subscription plan (if present)
        subscription_plan = (
            db.query(models.user.Subscription)
            .filter(models.user.Subscription.id == subscriber.subscription_id)
            .first()
        )

        # Determine renewal date: prefer invoice.period_end, fall back to lines[].period.end, else +30d
        period_end = None
        if invoice.get("period_end"):
            period_end = invoice.get("period_end")
        else:
            try:
                lines = invoice.get("lines", {}).get("data", []) or []
                for line in lines:
                    p = line.get("period") or {}
                    if p and p.get("end"):
                        period_end = p.get("end")
                        break
            except Exception:
                period_end = None

        if period_end:
            try:
                renew_dt = datetime.utcfromtimestamp(int(period_end))
            except Exception:
                renew_dt = datetime.utcnow() + timedelta(days=30)
        else:
            renew_dt = datetime.utcnow() + timedelta(days=30)

        # Update subscriber state with credit rollover
        if subscription_plan:
            # Only add credits for RENEWALS, not new subscriptions
            # New subscriptions are already handled by checkout.session.completed webhook
            # Check if this is a renewal by looking at billing_reason
            billing_reason = invoice.get("billing_reason", "")
            
            if billing_reason == "subscription_cycle":
                # This is a renewal - add credits
                subscriber.current_credits += subscription_plan.credits
                logger.info(f"Renewal: Added {subscription_plan.credits} credits to subscriber {subscriber.id}")
            elif billing_reason in ["subscription_create", "subscription_update"]:
                # New subscription or update - credits already added by checkout.session.completed
                logger.info(f"New/Updated subscription: Skipping credit addition (billing_reason={billing_reason})")
            else:
                # Unknown billing reason - log and skip to be safe
                logger.warning(f"Unknown billing_reason '{billing_reason}' - skipping credit addition to avoid duplicates")
            
        # Clear frozen credits if reactivating within 30 days
        if subscriber.frozen_credits > 0 and subscriber.frozen_at:
            days_since_freeze = (datetime.utcnow() - subscriber.frozen_at).days
            if days_since_freeze <= 30:
                # Restore frozen credits
                subscriber.current_credits += subscriber.frozen_credits
                logger.info(f"Restored {subscriber.frozen_credits} frozen credits for subscriber {subscriber.id}")
            # Clear freeze tracking
            subscriber.frozen_credits = 0
            subscriber.frozen_at = None
            
        subscriber.subscription_renew_date = renew_dt
        subscriber.is_active = True
        subscriber.subscription_status = "active"
        subscriber.last_active_date = datetime.utcnow()

        # Get user for logging BEFORE commit
        user = (
            db.query(models.user.User)
            .filter(models.user.User.id == subscriber.user_id)
            .first()
        )

        db.commit()

        # Record payment in payments table (use invoice.amount_paid if present)
        try:
            amount = None
            amt_cents = (
                invoice.get("amount_paid")
                or invoice.get("total")
                or invoice.get("amount_due")
            )
            if amt_cents is not None:
                try:
                    amount = float(amt_cents) / 100.0
                except Exception:
                    amount = None

            # As a fallback, if we have a subscription_plan with a price string
            if (
                amount is None
                and subscription_plan
                and getattr(subscription_plan, "price", None)
            ):
                try:
                    amount = float(subscription_plan.price)
                except Exception:
                    amount = None

            if amount is not None:
                try:
                    stripe_invoice_id = invoice.get("id")
                    # Some invoices include a checkout session id on the invoice
                    stripe_session_id = invoice.get("checkout_session") or None
                    currency = (invoice.get("currency") or "usd").lower()
                    subscriber_id = subscriber.id if subscriber else None
                    subscription_id = subscriber.subscription_id if subscriber else None

                    logger.info(
                        "Attempting to record invoice payment: subscription_id=%s subscriber_id=%s invoice_id=%s charge_amt_cents=%s amount=%s currency=%s",
                        subscription_id,
                        subscriber_id,
                        stripe_invoice_id,
                        amt_cents,
                        amount,
                        currency,
                    )

                    # Convert to USD when needed using charge -> balance transaction
                    usd_amount = None
                    try:
                        if currency == "usd":
                            usd_amount = float(amount)
                        else:
                            # invoice may include a charge id
                            charge_id = invoice.get("charge")
                            if not charge_id:
                                # try payment_intent -> charges
                                payment_intent_id = invoice.get("payment_intent")
                                if payment_intent_id:
                                    try:
                                        pi = stripe.PaymentIntent.retrieve(
                                            payment_intent_id
                                        )
                                        charges = (
                                            pi.get("charges", {}).get("data", []) or []
                                        )
                                        if charges:
                                            charge_id = charges[0].get("id")
                                    except Exception:
                                        charge_id = None

                            if charge_id:
                                try:
                                    ch = stripe.Charge.retrieve(charge_id)
                                    bt_id = ch.get("balance_transaction")
                                    if bt_id:
                                        bt = stripe.BalanceTransaction.retrieve(bt_id)
                                        if bt and bt.get("currency") == "usd":
                                            usd_amount = (
                                                float(bt.get("amount", 0)) / 100.0
                                            )
                                        elif bt and bt.get("exchange_rate"):
                                            try:
                                                usd_amount = (
                                                    float(bt.get("amount", 0)) / 100.0
                                                ) * float(bt.get("exchange_rate"))
                                            except Exception:
                                                usd_amount = None
                                except Exception:
                                    usd_amount = None
                    except Exception:
                        usd_amount = None

                    if usd_amount is None and currency == "usd":
                        usd_amount = float(amount)

                    # Insert minimal payment record: subscriber_id, amount (USD), payment_date, created_at
                    # Check if payment already exists for this invoice to avoid duplicates
                    stripe_invoice_id = invoice.get("id")
                    existing_payment = db.execute(
                        text(
                            "SELECT id FROM payments WHERE subscriber_id = :subscriber_id "
                            "AND amount = :amt AND payment_date = :pd"
                        ),
                        {
                            "subscriber_id": subscriber_id,
                            "amt": usd_amount,
                            "pd": datetime.utcnow().date(),  # Check by date only
                        },
                    ).fetchone()
                    
                    if existing_payment:
                        logger.info(
                            f"Payment already recorded for subscriber {subscriber_id} on {datetime.utcnow().date()}, invoice {stripe_invoice_id}"
                        )
                    else:
                        db.execute(
                            text(
                                "INSERT INTO payments (subscriber_id, amount, payment_date, created_at) "
                                "VALUES (:subscriber_id, :amt, :pd, now()) "
                                "ON CONFLICT DO NOTHING"
                            ),
                            {
                                "subscriber_id": subscriber_id,
                                "amt": usd_amount,
                                "pd": datetime.utcnow(),
                            },
                        )
                        db.commit()
                        logger.info(
                            f"Recorded renewal payment of {usd_amount} usd for subscriber {subscriber_id}"
                        )
                except Exception:
                    logger.exception(
                        "Could not record payment in payments table for invoice %s",
                        invoice.get("id"),
                    )
                    try:
                        db.rollback()
                    except Exception:
                        pass
        except Exception:
            logger.exception(
                "Unexpected error while attempting to record invoice payment"
            )

        logger.info(
            "Renewed subscription for user %s (subscriber %s). Next renewal: %s. "
            "Credits reset to %s",
            user.email if user else subscriber.user_id,
            subscriber.id,
            subscriber.subscription_renew_date,
            subscription_plan.credits if subscription_plan else 0,
        )

    except Exception as e:
        logger.exception(
            "Error handling invoice.payment_succeeded for invoice %s: %s",
            invoice.get("id"),
            e,
        )
        try:
            db.rollback()
        except Exception:
            pass
        raise

    # TODO: Send renewal confirmation email


async def handle_invoice_payment_failed(invoice, db: Session):
    """Handle failed payment."""
    logger.info(f"Processing invoice.payment_failed for invoice {invoice.get('id')}")

    try:
        stripe_subscription_id = invoice.get("subscription")
        if not stripe_subscription_id:
            lines = invoice.get("lines", {}).get("data", []) or []
            for line in lines:
                if line and line.get("subscription"):
                    stripe_subscription_id = line.get("subscription")
                    break

        if not stripe_subscription_id:
            logger.warning(
                "Failed invoice %s has no subscription id - skipping",
                invoice.get("id"),
            )
            return

        subscriber = (
            db.query(models.user.Subscriber)
            .filter(
                models.user.Subscriber.stripe_subscription_id == stripe_subscription_id
            )
            .first()
        )

        if not subscriber:
            # Try metadata user_id
            try:
                meta_user_id = invoice.get("metadata", {}).get("user_id")
                if meta_user_id:
                    try:
                        meta_user_id_int = int(meta_user_id)
                    except Exception:
                        meta_user_id_int = None
                    if meta_user_id_int:
                        subscriber = (
                            db.query(models.user.Subscriber)
                            .filter(models.user.Subscriber.user_id == meta_user_id_int)
                            .first()
                        )
            except Exception:
                pass

        if not subscriber:
            # Try finding user by Stripe customer id
            try:
                customer_id = invoice.get("customer")
                if customer_id:
                    user = (
                        db.query(models.user.User)
                        .filter(models.user.User.stripe_customer_id == customer_id)
                        .first()
                    )
                    if user:
                        subscriber = (
                            db.query(models.user.Subscriber)
                            .filter(models.user.Subscriber.user_id == user.id)
                            .first()
                        )
            except Exception:
                pass

        if not subscriber:
            # Last resort: create a minimal subscriber when we can identify the user via customer
            try:
                customer_id = invoice.get("customer")
                user = None
                if customer_id:
                    user = (
                        db.query(models.user.User)
                        .filter(models.user.User.stripe_customer_id == customer_id)
                        .first()
                    )
                if user:
                    # Try to map subscription plan via metadata price
                    subscription_plan = None
                    meta_price = invoice.get("metadata", {}).get("stripe_price_id")
                    if meta_price:
                        subscription_plan = (
                            db.query(models.user.Subscription)
                            .filter(
                                models.user.Subscription.stripe_price_id == meta_price
                            )
                            .first()
                        )
                    subscriber = (
                        db.query(models.user.Subscriber)
                        .filter(models.user.Subscriber.user_id == user.id)
                        .first()
                    )
                    if not subscriber:
                        subscriber = models.user.Subscriber(
                            user_id=user.id,
                            subscription_id=(
                                subscription_plan.id if subscription_plan else None
                            ),
                            current_credits=(
                                subscription_plan.credits if subscription_plan else 0
                            ),
                            subscription_start_date=datetime.utcnow(),
                            subscription_renew_date=(
                                datetime.utcnow() + timedelta(days=30)
                            ),
                            is_active=False,
                            stripe_subscription_id=stripe_subscription_id,
                            subscription_status="past_due",
                        )
                        db.add(subscriber)
                        # Don't commit here - commit once at the end with status update
            except Exception:
                pass

        if not subscriber:
            logger.error(
                "Subscriber not found for Stripe subscription %s (invoice %s)",
                stripe_subscription_id,
                invoice.get("id"),
            )
            return

        subscriber.subscription_status = "past_due"
        subscriber.is_active = False

        db.commit()

        user = (
            db.query(models.user.User)
            .filter(models.user.User.id == subscriber.user_id)
            .first()
        )
        logger.info(
            "Marked subscription past_due for user %s (subscriber %s)",
            user.email if user else subscriber.user_id,
            subscriber.id,
        )

    except Exception as e:
        logger.exception(
            "Error handling invoice.payment_failed for invoice %s: %s",
            invoice.get("id"),
            e,
        )
        try:
            db.rollback()
        except Exception:
            pass
        raise


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

    # Freeze credits when subscription is canceled
    subscriber.frozen_credits = subscriber.current_credits
    subscriber.frozen_at = datetime.utcnow()
    subscriber.current_credits = 0
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
        f"Canceled subscription for user {user.email if user else subscriber.user_id}. Froze {subscriber.frozen_credits} credits."
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


async def handle_invoice_payment_action_required(invoice, db: Session):
    """Handle payment action required (3D Secure authentication needed)."""
    logger.info(
        f"Processing invoice.payment_action_required for invoice {invoice.get('id')}"
    )

    try:
        stripe_subscription_id = invoice.get("subscription")
        if not stripe_subscription_id:
            logger.warning(
                "Invoice %s has no subscription id - skipping",
                invoice.get("id"),
            )
            return

        # Find subscriber
        subscriber = (
            db.query(models.user.Subscriber)
            .filter(
                models.user.Subscriber.stripe_subscription_id == stripe_subscription_id
            )
            .first()
        )

        if not subscriber:
            logger.error(
                "Subscriber not found for Stripe subscription %s (invoice %s)",
                stripe_subscription_id,
                invoice.get("id"),
            )
            return

        # Update subscription status to indicate payment action is required
        subscriber.subscription_status = "action_required"

        db.commit()

        user = (
            db.query(models.user.User)
            .filter(models.user.User.id == subscriber.user_id)
            .first()
        )
        logger.info(
            "Payment action required for user %s (subscriber %s). "
            "User needs to authenticate payment method.",
            user.email if user else subscriber.user_id,
            subscriber.id,
        )

        # TODO: Send email notification to user about payment action required

    except Exception as e:
        logger.exception(
            "Error handling invoice.payment_action_required for invoice %s: %s",
            invoice.get("id"),
            e,
        )
        try:
            db.rollback()
        except Exception:
            pass
        raise


async def handle_invoice_upcoming(invoice, db: Session):
    """Handle upcoming invoice (for sending renewal reminders)."""
    logger.info(f"Processing invoice.upcoming for invoice {invoice.get('id')}")

    try:
        stripe_subscription_id = invoice.get("subscription")
        if not stripe_subscription_id:
            logger.debug(
                "Invoice %s has no subscription id (may be one-off) - skipping",
                invoice.get("id"),
            )
            return

        # Find subscriber
        subscriber = (
            db.query(models.user.Subscriber)
            .filter(
                models.user.Subscriber.stripe_subscription_id == stripe_subscription_id
            )
            .first()
        )

        if not subscriber:
            logger.debug(
                "Subscriber not found for Stripe subscription %s (invoice %s) - skipping reminder",
                stripe_subscription_id,
                invoice.get("id"),
            )
            return

        # Determine renewal date from invoice
        period_end = invoice.get("period_end")
        if period_end:
            try:
                renew_dt = datetime.utcfromtimestamp(int(period_end))
                subscriber.subscription_renew_date = renew_dt
                db.commit()
            except Exception:
                pass

        user = (
            db.query(models.user.User)
            .filter(models.user.User.id == subscriber.user_id)
            .first()
        )
        logger.info(
            "Upcoming invoice for user %s (subscriber %s). Renewal date: %s",
            user.email if user else subscriber.user_id,
            subscriber.id,
            subscriber.subscription_renew_date,
        )

        # TODO: Send renewal reminder email to user

    except Exception as e:
        logger.exception(
            "Error handling invoice.upcoming for invoice %s: %s",
            invoice.get("id"),
            e,
        )
        try:
            db.rollback()
        except Exception:
            pass


async def handle_subscription_paused(subscription_obj, db: Session):
    """Handle subscription pause."""
    logger.info(
        f"Processing customer.subscription.paused for subscription {subscription_obj['id']}"
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

    # Update subscription status
    subscriber.subscription_status = "paused"
    subscriber.is_active = False

    db.commit()

    # Get user
    user = (
        db.query(models.user.User)
        .filter(models.user.User.id == subscriber.user_id)
        .first()
    )

    logger.info(
        f"Paused subscription for user {user.email if user else subscriber.user_id}"
    )

    # TODO: Send pause confirmation email


async def handle_subscription_resumed(subscription_obj, db: Session):
    """Handle subscription resume from pause."""
    logger.info(
        f"Processing customer.subscription.resumed for subscription {subscription_obj['id']}"
    )

    stripe_subscription_id = subscription_obj["id"]
    status = subscription_obj.get("status", "active")

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
    subscriber.is_active = True

    # Update renewal date if available
    current_period_end = subscription_obj.get("current_period_end")
    if current_period_end:
        try:
            renew_dt = datetime.utcfromtimestamp(int(current_period_end))
            subscriber.subscription_renew_date = renew_dt
        except Exception:
            pass

    db.commit()

    # Get user
    user = (
        db.query(models.user.User)
        .filter(models.user.User.id == subscriber.user_id)
        .first()
    )

    logger.info(
        f"Resumed subscription for user {user.email if user else subscriber.user_id}. "
        f"Status: {status}"
    )

    # TODO: Send resume confirmation email


@router.get("/my-subscription", response_model=schemas.subscription.SubscriberResponse)
def get_my_subscription(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """Get current user's subscription details."""
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.user_id == effective_user.id)
        .first()
    )

    if not subscriber:
        raise HTTPException(
            status_code=404, detail="No subscription found for this user"
        )
    # Enrich response with plan name and plan total credits
    plan_name = None
    plan_total_credits = None
    max_seats = 1
    if subscriber.subscription_id:
        plan = (
            db.query(models.user.Subscription)
            .filter(models.user.Subscription.id == subscriber.subscription_id)
            .first()
        )
        if plan:
            plan_name = plan.name
            plan_total_credits = plan.credits
            max_seats = plan.max_seats or 1

    # Calculate remaining seats
    seats_used = subscriber.seats_used or 0
    purchased_seats = subscriber.purchased_seats or 0
    total_seats = max_seats + purchased_seats  # Current plan seats + accumulated seats
    remaining_seats = max(0, total_seats - seats_used)

    # `Subscriber` model may not have `subscription_status` on older schemas.
    # Compute a safe value: prefer the attribute if present, otherwise derive
    # from `is_active` (active/inactive).
    status = getattr(subscriber, "subscription_status", None)
    if status is None:
        status = "active" if subscriber.is_active else "inactive"

    return {
        "id": subscriber.id,
        "user_id": subscriber.user_id,
        "subscription_id": subscriber.subscription_id,
        "current_credits": subscriber.current_credits,
        "total_spending": subscriber.total_spending,
        "seats_used": seats_used,
        "remaining_seats": remaining_seats,
        "subscription_start_date": subscriber.subscription_start_date,
        "subscription_renew_date": subscriber.subscription_renew_date,
        "is_active": subscriber.is_active,
        "stripe_subscription_id": subscriber.stripe_subscription_id,
        "subscription_status": status,
        "auto_renew": subscriber.auto_renew,
        "plan_name": plan_name,
        "plan_total_credits": plan_total_credits,
    }


@router.post("/cancel-subscription")
async def cancel_subscription(
    current_user: models.user.User = Depends(require_main_account),
    db: Session = Depends(get_db),
):
    """
    Cancel the current subscription.

    The subscription will remain active until the end of the current billing period.
    """
    # `require_main_account` ensures only main accounts reach here

    # Get subscriber
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.user_id == current_user.id)
        .first()
    )

    if not subscriber or not subscriber.stripe_subscription_id:
        raise HTTPException(status_code=404, detail="No active subscription found")

    try:
        # Delete the Stripe subscription immediately to prevent future charges
        stripe.Subscription.delete(subscriber.stripe_subscription_id)

        # Update subscriber status in database
        subscriber.is_active = False
        subscriber.subscription_status = "canceled"
        subscriber.stripe_subscription_id = None
        subscriber.auto_renew = False
        db.commit()

        logger.info(
            f"Canceled and deleted Stripe subscription {subscriber.stripe_subscription_id} for user {current_user.email}"
        )

        return {
            "message": "Subscription has been canceled immediately. You will not be charged again.",
            "status": "canceled",
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error canceling subscription: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to cancel subscription: {str(e)}"
        )


@router.post("/toggle-auto-renew")
async def toggle_auto_renew(
    current_user: models.user.User = Depends(require_main_account),
    db: Session = Depends(get_db),
):
    """
    Toggle auto-renewal setting for the current subscription in Stripe.
    
    When user clicks:
    - System checks if user has an active subscription
    - Gets current auto-renew status from database
    - Sends opposite value to Stripe (if currently True, sends False to disable)
    - Updates database to match
    
    Returns the new auto-renew state.
    """
    # Get subscriber
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.user_id == current_user.id)
        .first()
    )

    # Check if user has an active subscription
    if not subscriber:
        raise HTTPException(status_code=404, detail="No subscription found")
    
    if not subscriber.stripe_subscription_id:
        raise HTTPException(status_code=400, detail="No active Stripe subscription found")
    
    if not subscriber.is_active:
        raise HTTPException(status_code=400, detail="Subscription is not active")

    try:
        # Get current auto_renew status
        current_auto_renew = subscriber.auto_renew
        
        # Toggle: if currently True, set to False (disable auto-renewal)
        new_auto_renew = not current_auto_renew
        
        # Update Stripe subscription auto-renewal setting
        stripe.Subscription.modify(
            subscriber.stripe_subscription_id,
            cancel_at_period_end=not new_auto_renew  # If disabling auto-renew, cancel at period end
        )

        # Update database
        subscriber.auto_renew = new_auto_renew
        db.commit()

        if new_auto_renew:
            logger.info(f"Auto-renew enabled for user {current_user.email}, Stripe subscription {subscriber.stripe_subscription_id}")
            return {
                "message": "Auto-renewal enabled. Your subscription will automatically renew at the end of your billing period.",
                "auto_renew": True,
                "status": "active",
                "next_billing_date": subscriber.subscription_renew_date,
            }
        else:
            logger.info(f"Auto-renew disabled for user {current_user.email}, Stripe subscription {subscriber.stripe_subscription_id}")
            return {
                "message": "Auto-renewal disabled. You will have access until the end of your current billing period and will not be charged again.",
                "auto_renew": False,
                "status": "scheduled_to_cancel",
                "access_until": subscriber.subscription_renew_date,
            }

    except stripe.error.StripeError as e:
        db.rollback()
        logger.error(f"Failed to toggle auto-renew for subscription {subscriber.stripe_subscription_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update subscription in Stripe: {str(e)}")


@router.post("/reactivate-subscription")
async def reactivate_subscription(
    current_user: models.user.User = Depends(require_main_account),
    db: Session = Depends(get_db),
):
    """
    Reactivate a subscription that was scheduled for cancellation.
    """
    # `require_main_account` ensures only main accounts reach here

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
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """Get user's wallet information including credits and spending history."""
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.user_id == effective_user.id)
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
        .filter(models.user.UnlockedLead.user_id == effective_user.id)
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
    admin: models.user.AdminUser = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    """
    Admin endpoint to update subscription tiers pricing (Starter, Professional, Enterprise, Custom).

    Updates multiple tiers at once. Provide an array of tier updates.
    - Standard tiers (Starter, Professional, Enterprise): monthly_price, credits, seats
    - Custom tier: credit_price, seat_price

    Only admin users can access this endpoint.
    """
    # Caller authorized via `require_admin` dependency

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


# --- Missing webhook handlers (safe stubs) ---------------------------------
async def handle_invoice_payment_action_required(invoice, db: Session):
    """Handle invoices that require payment action (e.g., 3D Secure)."""
    logger.info(
        "Processing invoice.payment_action_required for invoice %s", invoice.get("id")
    )
    try:
        # Mark subscriber as action_required/past_due where possible
        stripe_subscription_id = invoice.get("subscription")
        if not stripe_subscription_id:
            logger.debug("No subscription id on invoice %s", invoice.get("id"))
            return

        subscriber = (
            db.query(models.user.Subscriber)
            .filter(
                models.user.Subscriber.stripe_subscription_id == stripe_subscription_id
            )
            .first()
        )

        if subscriber:
            subscriber.subscription_status = "action_required"
            subscriber.is_active = False
            db.commit()
            logger.info("Marked subscriber %s as action_required", subscriber.id)
    except Exception as e:
        logger.exception("Error in handle_invoice_payment_action_required: %s", e)
        try:
            db.rollback()
        except Exception:
            pass


async def handle_invoice_upcoming(invoice, db: Session):
    """Handle upcoming invoice events (reminders)."""
    logger.info("Processing invoice.upcoming for invoice %s", invoice.get("id"))
    # Currently we only log. Optionally notify the user via email in future.
    return


async def handle_subscription_paused(subscription_obj, db: Session):
    """Handle subscription paused events from Stripe."""
    logger.info(
        "Processing customer.subscription.paused for subscription %s",
        subscription_obj.get("id"),
    )
    try:
        stripe_subscription_id = subscription_obj.get("id")
        subscriber = (
            db.query(models.user.Subscriber)
            .filter(
                models.user.Subscriber.stripe_subscription_id == stripe_subscription_id
            )
            .first()
        )
        if subscriber:
            subscriber.subscription_status = subscription_obj.get("status", "paused")
            subscriber.is_active = False
            db.commit()
            logger.info("Paused subscriber %s", subscriber.id)
    except Exception as e:
        logger.exception("Error in handle_subscription_paused: %s", e)
        try:
            db.rollback()
        except Exception:
            pass


async def handle_subscription_resumed(subscription_obj, db: Session):
    """Handle subscription resumed events from Stripe."""
    logger.info(
        "Processing customer.subscription.resumed for subscription %s",
        subscription_obj.get("id"),
    )
    try:
        stripe_subscription_id = subscription_obj.get("id")
        subscriber = (
            db.query(models.user.Subscriber)
            .filter(
                models.user.Subscriber.stripe_subscription_id == stripe_subscription_id
            )
            .first()
        )
        if subscriber:
            subscriber.subscription_status = subscription_obj.get("status", "active")
            subscriber.is_active = True
            db.commit()
            logger.info("Resumed subscriber %s", subscriber.id)
    except Exception as e:
        logger.exception("Error in handle_subscription_resumed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass


# ==================== ADD-ON MANAGEMENT ENDPOINTS ====================

@router.get("/my-add-ons")
def get_my_add_ons(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Get available add-ons for the current user's subscription tier.
    
    Returns earned but unredeemed add-ons and their availability based on tier.
    
    Response includes:
    - Which add-ons are available for current tier
    - How many credits/seats are earned but not yet redeemed
    - Last redemption timestamps
    """
    # Get subscriber information
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.user_id == effective_user.id)
        .first()
    )
    
    if not subscriber:
        raise HTTPException(
            status_code=404,
            detail="No subscription found. Please subscribe to a plan first."
        )
    
    # Get subscription plan to check tier and available add-ons
    subscription = None
    if subscriber.subscription_id:
        subscription = (
            db.query(models.user.Subscription)
            .filter(models.user.Subscription.id == subscriber.subscription_id)
            .first()
        )
        # Refresh to get latest data from database
        if subscription:
            db.refresh(subscription)
    
    if not subscription:
        return {
            "message": "No active subscription plan",
            "stay_active_bonus": {
                "available": False,
                "credits_earned": 0,
                "last_redeemed": None
            },
            "bonus_credits": {
                "available": False,
                "credits_earned": 0,
                "last_redeemed": None
            },
            "boost_pack": {
                "available": False,
                "credits_earned": 0,
                "seats_earned": 0,
                "last_redeemed": None
            }
        }
    
    return {
        "subscription_tier": subscription.name,
        "tier_level": subscription.tier_level,
        "stay_active_bonus": {
            "available": subscription.has_stay_active_bonus and (subscriber.stay_active_credits or 0) > 0,
            "credits_earned": subscriber.stay_active_credits or 0,
            "credit_value": 30,  # Stay Active = 30 credits
            "last_redeemed": subscriber.last_stay_active_redemption.isoformat() if subscriber.last_stay_active_redemption else None
        },
        "bonus_credits": {
            "available": subscription.has_bonus_credits and (subscriber.bonus_credits or 0) > 0,
            "credits_earned": subscriber.bonus_credits or 0,
            "credit_value": 50,  # Bonus Credits = 50 credits
            "last_redeemed": subscriber.last_bonus_redemption.isoformat() if subscriber.last_bonus_redemption else None
        },
        "boost_pack": {
            "available": subscription.has_boost_pack and ((subscriber.boost_pack_credits or 0) > 0 or (subscriber.boost_pack_seats or 0) > 0),
            "credits_earned": subscriber.boost_pack_credits or 0,
            "seats_earned": subscriber.boost_pack_seats or 0,
            "credit_value": 100,  # Boost Pack = 100 credits
            "seat_value": 1,  # Boost Pack = 1 seat
            "last_redeemed": subscriber.last_boost_redemption.isoformat() if subscriber.last_boost_redemption else None
        }
    }


@router.post("/redeem-add-on")
async def redeem_add_on(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Redeem all earned add-ons automatically and receive a detailed congratulations message.
    
    **No Request Body Required**
    
    **Process:**
    1. Automatically detects all available add-ons for user's subscription tier
    2. Redeems all earned credits/seats from all add-ons
    3. Returns detailed congratulations message with subscription benefits
    
    **Availability by Tier:**
    - Starter: stay_active_bonus (30 credits)
    - Professional: stay_active_bonus (30 credits), bonus_credits (50 credits)
    - Enterprise: stay_active_bonus (30 credits), bonus_credits (50 credits), boost_pack (100 credits + 1 seat)
    - Custom: stay_active_bonus (30 credits), bonus_credits (50 credits), boost_pack (100 credits + 1 seat)
    """
    # Get subscriber
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.user_id == effective_user.id)
        .first()
    )
    
    if not subscriber:
        raise HTTPException(
            status_code=404,
            detail="No subscription found. Please subscribe to a plan first."
        )
    
    # Get subscription to check tier
    subscription = None
    if subscriber.subscription_id:
        subscription = (
            db.query(models.user.Subscription)
            .filter(models.user.Subscription.id == subscriber.subscription_id)
            .first()
        )
    
    if not subscription:
        raise HTTPException(
            status_code=403,
            detail="No active subscription plan. Please subscribe first."
        )
    
    # Track all redeemed add-ons
    total_credits_added = 0
    total_seats_added = 0
    redeemed_addons = []
    
    # Redeem Stay Active Bonus (30 credits)
    if subscription.has_stay_active_bonus:
        earned_credits = subscriber.stay_active_credits or 0
        if earned_credits > 0:
            subscriber.current_credits += earned_credits
            total_credits_added += earned_credits
            subscriber.stay_active_credits = 0
            subscriber.last_stay_active_redemption = datetime.utcnow()
            redeemed_addons.append(f"Stay Active Bonus: {earned_credits} credits")
    
    # Redeem Bonus Credits (50 credits)
    if subscription.has_bonus_credits:
        earned_credits = subscriber.bonus_credits or 0
        if earned_credits > 0:
            subscriber.current_credits += earned_credits
            total_credits_added += earned_credits
            subscriber.bonus_credits = 0
            subscriber.last_bonus_redemption = datetime.utcnow()
            redeemed_addons.append(f"Bonus Credits: {earned_credits} credits")
    
    # Redeem Boost Pack (100 credits + 1 seat)
    if subscription.has_boost_pack:
        earned_credits = subscriber.boost_pack_credits or 0
        earned_seats = subscriber.boost_pack_seats or 0
        if earned_credits > 0 or earned_seats > 0:
            subscriber.current_credits += earned_credits
            total_credits_added += earned_credits
            total_seats_added += earned_seats
            subscriber.boost_pack_credits = 0
            subscriber.boost_pack_seats = 0
            subscriber.last_boost_redemption = datetime.utcnow()
            redeemed_addons.append(f"Boost Pack: {earned_credits} credits + {earned_seats} seat")
    
    # Check if any add-ons were redeemed
    if total_credits_added == 0 and total_seats_added == 0:
        raise HTTPException(
            status_code=400,
            detail=f"No add-ons available to redeem. Keep using the platform to earn rewards on your {subscription.name} plan!"
        )
    
    # Commit all changes
    db.commit()
    db.refresh(subscriber)
    
    # Build detailed congratulations message
    subscription_type = subscription.name  # "Starter", "Professional", "Enterprise", "Custom"
    
    congratulations_message = f"🎉 Congratulations! Thank you for subscribing to the {subscription_type} plan! 🎉\n\n"
    congratulations_message += f"You have successfully redeemed your rewards:\n"
    
    for addon in redeemed_addons:
        congratulations_message += f"  ✓ {addon}\n"
    
    congratulations_message += f"\nTotal Benefits Received:\n"
    if total_credits_added > 0:
        congratulations_message += f"  • {total_credits_added} credits added to your account\n"
    if total_seats_added > 0:
        congratulations_message += f"  • {total_seats_added} additional seat(s)\n"
    
    congratulations_message += f"\nCurrent Account Status:\n"
    congratulations_message += f"  • Total Credits: {subscriber.current_credits}\n"
    congratulations_message += f"  • Subscription: {subscription_type}\n"
    
    return {
        "success": True,
        "message": congratulations_message,
        "subscription_type": subscription_type,
        "total_credits_added": total_credits_added,
        "total_seats_added": total_seats_added,
        "new_credit_balance": subscriber.current_credits,
        "redeemed_addons": redeemed_addons,
        "timestamp": datetime.utcnow().isoformat()
    }
