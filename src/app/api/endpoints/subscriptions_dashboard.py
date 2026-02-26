import logging
from datetime import datetime, timedelta
from typing import Optional

import stripe
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import String, case, func, or_
from sqlalchemy.orm import Session

from src.app import models, schemas
from src.app.api.deps import require_admin_token
from src.app.core.database import get_db
from src.app.api.endpoints.subscription import _update_all_tiers_pricing_impl

router = APIRouter(prefix="/admin/subscriptions", tags=["Admin - Subscriptions"])

logger = logging.getLogger("uvicorn.error")


@router.put(
    "/update-all-tiers-pricing",
    dependencies=[Depends(require_admin_token)],
)
def admin_update_all_tiers_pricing(
    data: schemas.subscription.UpdateAllTiersPricingRequest,
    db: Session = Depends(get_db),
):
    """
    Admin endpoint: Update subscription tiers pricing (Starter, Professional, Enterprise, Custom).

    This is the admin-facing version of the pricing update API, used by the
    Subscription Management → Pricing screen.

    It mirrors the legacy `/subscription/admin/update-all-tiers-pricing` endpoint
    but is grouped under the admin subscriptions router and protected by the
    `require_admin_token` dependency.
    """
    return _update_all_tiers_pricing_impl(data, db)


@router.get("/dashboard", dependencies=[Depends(require_admin_token)])
def subscriptions_dashboard(
    # Subscription Status Filter
    subscription_status: Optional[str] = Query(
        None, description="Filter by subscription status: active, inactive"
    ),
    # Plan Tier Filter
    plan_tier: Optional[str] = Query(
        None,
        description="Filter by plan: Starter, Professional, Enterprise, Custom, None",
    ),
    # Current Credits Range
    credits_min: Optional[int] = Query(None, description="Minimum current credits"),
    credits_max: Optional[int] = Query(None, description="Maximum current credits"),
    # Total Spending Range
    spending_min: Optional[int] = Query(None, description="Minimum total spending"),
    spending_max: Optional[int] = Query(None, description="Maximum total spending"),
    # Renewal Date Filters
    renewal_quick_filter: Optional[str] = Query(
        None,
        description="Quick renewal filter: last_7_days, last_30_days, last_90_days",
    ),
    renewal_from: Optional[str] = Query(
        None, description="Custom renewal start date (YYYY-MM-DD)"
    ),
    renewal_to: Optional[str] = Query(
        None, description="Custom renewal end date (YYYY-MM-DD)"
    ),
    # User Role Filter
    user_role: Optional[str] = Query(
        None, description="Filter by user role: Contractor, Supplier"
    ),
    # Audience Type (User Type) Filter
    audience_type: Optional[str] = Query(
        None, description="Filter by user type (trade)"
    ),
    # Pagination
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(100, ge=1, le=500, description="Items per page"),
    db: Session = Depends(get_db),
):
    """
    Admin endpoint: Subscription Management Dashboard.

    Returns KPIs, filters, and paginated subscription data for all users.

    KPIs include:
    - Active Subscriptions
    - MRR (Monthly Recurring Revenue)
    - Churn Rate
    - Trial Conversion
    - Average Credits
    - Past Due Count
    - Monthly Cancellations
    - Average Lifetime Value
    """

    # ========================================================================
    # Helper Functions
    # ========================================================================
    def calc_percentage_change(current, previous):
        if previous == 0:
            return 0 if current == 0 else 100
        return round(((current - previous) / previous) * 100, 1)

    # ========================================================================
    # Date Range Calculations
    # ========================================================================
    today = datetime.utcnow()
    thirty_days_ago = today - timedelta(days=30)
    seven_days_ago = today - timedelta(days=7)
    ninety_days_ago = today - timedelta(days=90)
    sixty_days_ago = today - timedelta(days=60)

    # ========================================================================
    # KPI Calculations
    # ========================================================================

    # 1. Active Subscriptions (is_active = True)
    active_subscriptions = (
        db.query(func.count(models.user.Subscriber.id))
        .join(models.user.User, models.user.Subscriber.user_id == models.user.User.id)
        .filter(
            models.user.Subscriber.is_active == True,
            models.user.User.approved_by_admin == "approved",
        )
        .scalar()
        or 0
    )

    # Active subscriptions 30 days ago (for comparison)
    active_subscriptions_30d_ago = (
        db.query(func.count(models.user.Subscriber.id))
        .join(models.user.User, models.user.Subscriber.user_id == models.user.User.id)
        .filter(
            models.user.Subscriber.is_active == True,
            models.user.User.approved_by_admin == "approved",
            models.user.Subscriber.subscription_start_date <= thirty_days_ago,
        )
        .scalar()
        or 0
    )

    # 2. MRR (Monthly Recurring Revenue) - Calculate from active subscriptions
    # For active subscriptions, get their plan prices
    mrr_result = (
        db.query(
            func.sum(
                case(
                    (models.user.Subscription.name == "Starter", 49.99),
                    (models.user.Subscription.name == "Professional", 99.99),
                    (models.user.Subscription.name == "Enterprise", 199.99),
                    else_=0,
                )
            )
        )
        .select_from(models.user.Subscriber)
        .join(models.user.User, models.user.Subscriber.user_id == models.user.User.id)
        .outerjoin(
            models.user.Subscription,
            models.user.Subscriber.subscription_id == models.user.Subscription.id,
        )
        .filter(
            models.user.Subscriber.is_active == True,
            models.user.User.approved_by_admin == "approved",
        )
        .scalar()
        or 0
    )
    mrr = round(float(mrr_result), 2)

    # MRR 30 days ago (for comparison)
    mrr_30d_ago_result = (
        db.query(
            func.sum(
                case(
                    (models.user.Subscription.name == "Starter", 49.99),
                    (models.user.Subscription.name == "Professional", 99.99),
                    (models.user.Subscription.name == "Enterprise", 199.99),
                    else_=0,
                )
            )
        )
        .select_from(models.user.Subscriber)
        .join(models.user.User, models.user.Subscriber.user_id == models.user.User.id)
        .outerjoin(
            models.user.Subscription,
            models.user.Subscriber.subscription_id == models.user.Subscription.id,
        )
        .filter(
            models.user.Subscriber.is_active == True,
            models.user.User.approved_by_admin == "approved",
            models.user.Subscriber.subscription_start_date <= thirty_days_ago,
        )
        .scalar()
        or 0
    )
    mrr_30d_ago = round(float(mrr_30d_ago_result), 2)

    # 3. Churn Rate (cancelled in last 30 days / active at start of period)
    # Count subscriptions that were canceled in last 30 days (using frozen_at field)
    churned_last_30_days = (
        db.query(func.count(models.user.Subscriber.id))
        .join(models.user.User, models.user.Subscriber.user_id == models.user.User.id)
        .filter(
            models.user.Subscriber.subscription_status == "canceled",
            models.user.Subscriber.frozen_at >= thirty_days_ago,
            models.user.Subscriber.frozen_at <= today,
            models.user.User.approved_by_admin == "approved",
        )
        .scalar()
        or 0
    )

    # Total active at start of period (30 days ago)
    active_at_start = active_subscriptions_30d_ago
    churn_rate = (
        round((churned_last_30_days / active_at_start * 100), 1)
        if active_at_start > 0
        else 0
    )

    # Churn rate 60-30 days ago (for comparison)
    churned_60_30_days = (
        db.query(func.count(models.user.Subscriber.id))
        .join(models.user.User, models.user.Subscriber.user_id == models.user.User.id)
        .filter(
            models.user.Subscriber.subscription_status == "canceled",
            models.user.Subscriber.frozen_at >= sixty_days_ago,
            models.user.Subscriber.frozen_at < thirty_days_ago,
            models.user.User.approved_by_admin == "approved",
        )
        .scalar()
        or 0
    )

    active_60d_ago = (
        db.query(func.count(models.user.Subscriber.id))
        .join(models.user.User, models.user.Subscriber.user_id == models.user.User.id)
        .filter(
            models.user.Subscriber.is_active == True,
            models.user.User.approved_by_admin == "approved",
            models.user.Subscriber.subscription_start_date <= sixty_days_ago,
        )
        .scalar()
        or 0
    )
    churn_rate_prev = (
        round((churned_60_30_days / active_60d_ago * 100), 1)
        if active_60d_ago > 0
        else 0
    )

    # 4. Trial Conversion (users who activated subscription after trial period)
    # Count users who have trial_credits_used = True and is_active = True
    trial_conversions = (
        db.query(func.count(models.user.Subscriber.id))
        .join(models.user.User, models.user.Subscriber.user_id == models.user.User.id)
        .filter(
            models.user.Subscriber.trial_credits_used == True,
            models.user.Subscriber.is_active == True,
            models.user.User.approved_by_admin == "approved",
        )
        .scalar()
        or 0
    )

    # Total users who used trial
    total_trial_users = (
        db.query(func.count(models.user.Subscriber.id))
        .join(models.user.User, models.user.Subscriber.user_id == models.user.User.id)
        .filter(
            models.user.Subscriber.trial_credits_used == True,
            models.user.User.approved_by_admin == "approved",
        )
        .scalar()
        or 0
    )

    trial_conversion_rate = (
        round((trial_conversions / total_trial_users * 100), 1)
        if total_trial_users > 0
        else 0
    )

    # Previous period trial conversion (users who converted 30-60 days ago)
    trial_conversions_prev = (
        db.query(func.count(models.user.Subscriber.id))
        .join(models.user.User, models.user.Subscriber.user_id == models.user.User.id)
        .filter(
            models.user.Subscriber.trial_credits_used == True,
            models.user.Subscriber.is_active == True,
            models.user.User.approved_by_admin == "approved",
            models.user.Subscriber.subscription_start_date <= sixty_days_ago,
            models.user.Subscriber.subscription_start_date > ninety_days_ago,
        )
        .scalar()
        or 0
    )

    total_trial_users_prev = (
        db.query(func.count(models.user.Subscriber.id))
        .join(models.user.User, models.user.Subscriber.user_id == models.user.User.id)
        .filter(
            models.user.Subscriber.trial_credits_used == True,
            models.user.User.approved_by_admin == "approved",
            models.user.Subscriber.subscription_start_date <= sixty_days_ago,
        )
        .scalar()
        or 0
    )

    trial_conversion_rate_prev = (
        round((trial_conversions_prev / total_trial_users_prev * 100), 1)
        if total_trial_users_prev > 0
        else 0
    )

    # 5. Average Credits (average current_credits for all approved users)
    avg_credits_result = (
        db.query(func.avg(models.user.Subscriber.current_credits))
        .join(models.user.User, models.user.Subscriber.user_id == models.user.User.id)
        .filter(
            models.user.User.approved_by_admin == "approved",
        )
        .scalar()
        or 0
    )
    avg_credits = round(float(avg_credits_result), 1) if avg_credits_result else 0

    # Previous period
    avg_credits_prev_result = (
        db.query(func.avg(models.user.Subscriber.current_credits))
        .join(models.user.User, models.user.Subscriber.user_id == models.user.User.id)
        .filter(
            models.user.User.approved_by_admin == "approved",
            models.user.User.created_at <= thirty_days_ago,
        )
        .scalar()
        or 0
    )
    avg_credits_prev = (
        round(float(avg_credits_prev_result), 1) if avg_credits_prev_result else 0
    )

    # 6. Past Due (subscription_status = 'past_due')
    past_due = (
        db.query(func.count(models.user.Subscriber.id))
        .join(models.user.User, models.user.Subscriber.user_id == models.user.User.id)
        .filter(
            models.user.Subscriber.subscription_status == "past_due",
            models.user.User.approved_by_admin == "approved",
        )
        .scalar()
        or 0
    )

    past_due_prev = (
        db.query(func.count(models.user.Subscriber.id))
        .join(models.user.User, models.user.Subscriber.user_id == models.user.User.id)
        .filter(
            models.user.Subscriber.subscription_status == "past_due",
            models.user.User.approved_by_admin == "approved",
            models.user.User.created_at <= thirty_days_ago,
        )
        .scalar()
        or 0
    )

    # 7. Cancellation Monthly (cancelled in last 30 days)
    cancellations_monthly = churned_last_30_days
    cancellations_prev_month = churned_60_30_days

    # 8. Average Lifetime Value (average total_spending)
    avg_ltv_result = (
        db.query(func.avg(models.user.Subscriber.total_spending))
        .join(models.user.User, models.user.Subscriber.user_id == models.user.User.id)
        .filter(
            models.user.User.approved_by_admin == "approved",
        )
        .scalar()
        or 0
    )
    avg_ltv = round(float(avg_ltv_result), 2) if avg_ltv_result else 0

    avg_ltv_prev_result = (
        db.query(func.avg(models.user.Subscriber.total_spending))
        .join(models.user.User, models.user.Subscriber.user_id == models.user.User.id)
        .filter(
            models.user.User.approved_by_admin == "approved",
            models.user.User.created_at <= thirty_days_ago,
        )
        .scalar()
        or 0
    )
    avg_ltv_prev = round(float(avg_ltv_prev_result), 2) if avg_ltv_prev_result else 0

    # ========================================================================
    # Build Base Query for Data Table
    # ========================================================================
    base_query = (
        db.query(
            models.user.User,
            models.user.Subscriber,
            models.user.Subscription,
            models.user.Contractor,
            models.user.Supplier,
        )
        .outerjoin(
            models.user.Subscriber,
            models.user.User.id == models.user.Subscriber.user_id,
        )
        .outerjoin(
            models.user.Subscription,
            models.user.Subscriber.subscription_id == models.user.Subscription.id,
        )
        .outerjoin(
            models.user.Contractor,
            models.user.User.id == models.user.Contractor.user_id,
        )
        .outerjoin(
            models.user.Supplier, models.user.User.id == models.user.Supplier.user_id
        )
        .filter(models.user.User.approved_by_admin == "approved")
    )

    # ========================================================================
    # Apply Filters
    # ========================================================================

    # Subscription Status Filter (active/inactive)
    if subscription_status:
        if subscription_status.lower() == "active":
            base_query = base_query.filter(models.user.Subscriber.is_active == True)
        elif subscription_status.lower() == "inactive":
            base_query = base_query.filter(
                or_(
                    models.user.Subscriber.is_active == False,
                    models.user.Subscriber.is_active.is_(None),
                )
            )

    # Plan Tier Filter
    if plan_tier:
        if plan_tier.lower() == "none":
            base_query = base_query.filter(
                models.user.Subscriber.subscription_id.is_(None)
            )
        else:
            base_query = base_query.filter(models.user.Subscription.name == plan_tier)

    # Current Credits Range
    if credits_min is not None:
        base_query = base_query.filter(
            models.user.Subscriber.current_credits >= credits_min
        )
    if credits_max is not None:
        base_query = base_query.filter(
            models.user.Subscriber.current_credits <= credits_max
        )

    # Total Spending Range
    if spending_min is not None:
        base_query = base_query.filter(
            models.user.Subscriber.total_spending >= spending_min
        )
    if spending_max is not None:
        base_query = base_query.filter(
            models.user.Subscriber.total_spending <= spending_max
        )

    # Renewal Date Filters
    if renewal_quick_filter:
        if renewal_quick_filter == "last_7_days":
            base_query = base_query.filter(
                models.user.Subscriber.subscription_renew_date >= seven_days_ago
            )
        elif renewal_quick_filter == "last_30_days":
            base_query = base_query.filter(
                models.user.Subscriber.subscription_renew_date >= thirty_days_ago
            )
        elif renewal_quick_filter == "last_90_days":
            base_query = base_query.filter(
                models.user.Subscriber.subscription_renew_date >= ninety_days_ago
            )

    # Custom Renewal Date Range
    if renewal_from:
        try:
            from_date = datetime.strptime(renewal_from, "%Y-%m-%d")
            base_query = base_query.filter(
                models.user.Subscriber.subscription_renew_date >= from_date
            )
        except ValueError:
            pass  # Invalid date format, skip filter

    if renewal_to:
        try:
            to_date = datetime.strptime(renewal_to, "%Y-%m-%d")
            base_query = base_query.filter(
                models.user.Subscriber.subscription_renew_date <= to_date
            )
        except ValueError:
            pass  # Invalid date format, skip filter

    # User Role Filter
    if user_role:
        base_query = base_query.filter(models.user.User.role == user_role)

    # Audience Type (User Type) Filter
    if audience_type:
        # Check in both contractor and supplier user_type arrays
        base_query = base_query.filter(
            or_(
                models.user.Contractor.user_type.contains([audience_type]),
                models.user.Supplier.user_type.contains([audience_type]),
            )
        )

    # ========================================================================
    # Pagination
    # ========================================================================
    total_count = base_query.count()
    total_pages = (total_count + per_page - 1) // per_page

    offset = (page - 1) * per_page
    rows = (
        base_query.order_by(models.user.User.created_at.desc())
        .limit(per_page)
        .offset(offset)
        .all()
    )

    # ========================================================================
    # Build Data Table
    # ========================================================================
    data = []
    for user, subscriber, subscription, contractor, supplier in rows:
        # Get company name
        company_name = None
        if contractor:
            company_name = contractor.company_name
        elif supplier:
            company_name = supplier.company_name

        # Get user type (audience type)
        user_types = []
        if contractor and contractor.user_type:
            user_types = contractor.user_type
        elif supplier and supplier.user_type:
            user_types = supplier.user_type

        # Calculate individual LTV (total spending)
        ltv = subscriber.total_spending if subscriber else 0

        # Get plan name
        plan_name = subscription.name if subscription else "No Subscription"

        # Get subscription status (simplified to active/inactive)
        status = "Active" if (subscriber and subscriber.is_active) else "Inactive"

        data.append(
            {
                "user_id": user.id,
                "user_name": (
                    contractor.primary_contact_name
                    if contractor
                    else (supplier.primary_contact_name if supplier else None)
                ),
                "user_email": user.email,
                "company_name": company_name,
                "role": user.role,
                "plan": plan_name,
                "status": status,
                "available_credits": subscriber.current_credits if subscriber else 0,
                "trial_ends": (
                    subscriber.trial_credits_expires_at.isoformat()
                    if (subscriber and subscriber.trial_credits_expires_at)
                    else None
                ),
                "total_spending": subscriber.total_spending if subscriber else 0,
                "seats_used": subscriber.seats_used if subscriber else 0,
                "subscription_start": (
                    subscriber.subscription_start_date.isoformat()
                    if (subscriber and subscriber.subscription_start_date)
                    else None
                ),
                "renewal_date": (
                    subscriber.subscription_renew_date.isoformat()
                    if (subscriber and subscriber.subscription_renew_date)
                    else None
                ),
                "ltv": ltv,
                "user_types": user_types,
                "subscription_status_raw": (
                    subscriber.subscription_status if subscriber else "inactive"
                ),
            }
        )

    # ========================================================================
    # Return Response
    # ========================================================================
    return {
        "kpis": {
            "active_subscriptions": {
                "value": active_subscriptions,
                "change": calc_percentage_change(
                    active_subscriptions, active_subscriptions_30d_ago
                ),
            },
            "mrr": {
                "value": mrr,
                "change": calc_percentage_change(mrr, mrr_30d_ago),
            },
            "churn_rate": {
                "value": churn_rate,
                "change": calc_percentage_change(churn_rate, churn_rate_prev),
            },
            "trial_conversion": {
                "value": trial_conversion_rate,
                "change": calc_percentage_change(
                    trial_conversion_rate, trial_conversion_rate_prev
                ),
            },
            "avg_credits": {
                "value": avg_credits,
                "change": calc_percentage_change(avg_credits, avg_credits_prev),
            },
            "past_due": {
                "value": past_due,
                "change": calc_percentage_change(past_due, past_due_prev),
            },
            "cancellation_monthly": {
                "value": cancellations_monthly,
                "change": calc_percentage_change(
                    cancellations_monthly, cancellations_prev_month
                ),
            },
            "avg_lifetime_value": {
                "value": avg_ltv,
                "change": calc_percentage_change(avg_ltv, avg_ltv_prev),
            },
        },
        "data": data,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_items": total_count,
            "total_pages": total_pages,
        },
    }


@router.get("/dashboard/search", dependencies=[Depends(require_admin_token)])
def search_subscriptions(
    q: str = Query(..., min_length=2, description="Search query (min 2 characters)"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(25, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """
    Admin endpoint: Simple text search in subscriptions table.

    Searches across:
    - User email
    - User name (primary contact name)
    - Company name
    - User ID
    - Subscription plan name
    """
    from sqlalchemy import func, or_

    # Build search query
    search_term = f"%{q.lower()}%"

    # Build search conditions
    search_conditions = [
        # Search in user email
        func.lower(models.user.User.email).like(search_term),
        # Search in contractor name
        func.lower(models.user.Contractor.primary_contact_name).like(search_term),
        # Search in supplier name
        func.lower(models.user.Supplier.primary_contact_name).like(search_term),
        # Search in contractor company name
        func.lower(models.user.Contractor.company_name).like(search_term),
        # Search in supplier company name
        func.lower(models.user.Supplier.company_name).like(search_term),
        # Search in subscription plan name
        func.lower(models.user.Subscription.name).like(search_term),
    ]

    # Add user ID search if query is numeric
    if q.isdigit():
        search_conditions.append(models.user.User.id == int(q))

    # Build base query with joins
    base_query = (
        db.query(
            models.user.User,
            models.user.Subscriber,
            models.user.Subscription,
            models.user.Contractor,
            models.user.Supplier,
        )
        .outerjoin(
            models.user.Subscriber,
            models.user.User.id == models.user.Subscriber.user_id,
        )
        .outerjoin(
            models.user.Subscription,
            models.user.Subscriber.subscription_id == models.user.Subscription.id,
        )
        .outerjoin(
            models.user.Contractor,
            models.user.User.id == models.user.Contractor.user_id,
        )
        .outerjoin(
            models.user.Supplier, models.user.User.id == models.user.Supplier.user_id
        )
        .filter(
            models.user.User.approved_by_admin == "approved", or_(*search_conditions)
        )
    )

    # Get total count
    total_count = base_query.count()
    total_pages = (total_count + per_page - 1) // per_page

    # Apply pagination and order by most recent
    offset = (page - 1) * per_page
    rows = (
        base_query.order_by(models.user.User.created_at.desc())
        .limit(per_page)
        .offset(offset)
        .all()
    )

    # Build data table
    data = []
    for user, subscriber, subscription, contractor, supplier in rows:
        # Get company name
        company_name = None
        if contractor:
            company_name = contractor.company_name
        elif supplier:
            company_name = supplier.company_name

        # Get user type (audience type)
        user_types = []
        if contractor and contractor.user_type:
            user_types = contractor.user_type
        elif supplier and supplier.user_type:
            user_types = supplier.user_type

        # Calculate individual LTV (total spending)
        ltv = subscriber.total_spending if subscriber else 0

        # Get plan name
        plan_name = subscription.name if subscription else "No Subscription"

        # Get subscription status (simplified to active/inactive)
        status = "Active" if (subscriber and subscriber.is_active) else "Inactive"

        data.append(
            {
                "user_id": user.id,
                "user_name": (
                    contractor.primary_contact_name
                    if contractor
                    else (supplier.primary_contact_name if supplier else None)
                ),
                "user_email": user.email,
                "company_name": company_name,
                "role": user.role,
                "plan": plan_name,
                "status": status,
                "available_credits": subscriber.current_credits if subscriber else 0,
                "trial_ends": (
                    subscriber.trial_credits_expires_at.isoformat()
                    if (subscriber and subscriber.trial_credits_expires_at)
                    else None
                ),
                "total_spending": subscriber.total_spending if subscriber else 0,
                "seats_used": subscriber.seats_used if subscriber else 0,
                "subscription_start": (
                    subscriber.subscription_start_date.isoformat()
                    if (subscriber and subscriber.subscription_start_date)
                    else None
                ),
                "renewal_date": (
                    subscriber.subscription_renew_date.isoformat()
                    if (subscriber and subscriber.subscription_renew_date)
                    else None
                ),
                "ltv": ltv,
                "user_types": user_types,
                "subscription_status_raw": (
                    subscriber.subscription_status if subscriber else "inactive"
                ),
            }
        )

    # Return search results
    return {
        "data": data,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_items": total_count,
            "total_pages": total_pages,
        },
        "search_query": q,
    }


@router.get("/plans", dependencies=[Depends(require_admin_token)])
def get_all_subscription_plans(db: Session = Depends(get_db)):
    """
    Admin endpoint: Get all subscription plans including Custom tier.

    Returns:
    - Standard tiers (Starter, Professional, Enterprise): id, name, monthly_price, credits, seats, stripe_price_id, stripe_product_id
    - Custom tier: id, name, credit_price (price per 1 credit), seat_price (price per 1 seat), stripe_product_id
    """
    # Get all subscription plans
    all_plans = db.query(models.user.Subscription).all()

    plans_data = []

    for plan in all_plans:
        if plan.name.lower() == "custom":
            # For Custom tier, return credit_price and seat_price
            plans_data.append(
                {
                    "id": plan.id,
                    "name": plan.name,
                    "credit_price": plan.credit_price,  # Price per 1 credit
                    "seat_price": plan.seat_price,  # Price per 1 seat
                    "stripe_product_id": plan.stripe_product_id,
                }
            )
        else:
            # For standard tiers, return monthly_price, credits, seats
            plans_data.append(
                {
                    "id": plan.id,
                    "name": plan.name,
                    "monthly_price": plan.price,
                    "credits": plan.credits,
                    "seats": plan.max_seats,
                    "stripe_price_id": plan.stripe_price_id,
                    "stripe_product_id": plan.stripe_product_id,
                }
            )

    return {"plans": plans_data, "total": len(plans_data)}


@router.get("/credits-ledger", dependencies=[Depends(require_admin_token)])
def credits_ledger(
    # Pagination
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    # Filters
    subscription_status: Optional[str] = Query(
        None, description="Filter by subscription status"
    ),
    has_frozen_credits: Optional[bool] = Query(
        None, description="Filter users with frozen credits"
    ),
    has_trial_credits: Optional[bool] = Query(
        None, description="Filter users with active trial"
    ),
    user_role: Optional[str] = Query(
        None, description="Filter by role: Contractor, Supplier"
    ),
    # Search
    search: Optional[str] = Query(None, description="Search by email or name"),
    db: Session = Depends(get_db),
):
    """
    Admin endpoint: Get credits ledger for all users.

    Shows detailed credit status for each user including:
    - Current available credits
    - Total lifetime spending
    - Trial credits status
    - Frozen credits (from cancelled subscriptions)
    - Add-on credits
    """

    # Base query joining all necessary tables
    query = (
        db.query(
            models.user.User,
            models.user.Subscriber,
            models.user.Subscription,
        )
        .outerjoin(
            models.user.Subscriber,
            models.user.Subscriber.user_id == models.user.User.id,
        )
        .outerjoin(
            models.user.Subscription,
            models.user.Subscriber.subscription_id == models.user.Subscription.id,
        )
        .filter(models.user.User.approved_by_admin == "approved")
    )

    # Apply filters
    if subscription_status:
        query = query.filter(
            models.user.Subscriber.subscription_status == subscription_status
        )

    if has_frozen_credits is not None:
        if has_frozen_credits:
            query = query.filter(models.user.Subscriber.frozen_credits > 0)
        else:
            query = query.filter(
                or_(
                    models.user.Subscriber.frozen_credits == 0,
                    models.user.Subscriber.frozen_credits == None,
                )
            )

    if has_trial_credits is not None:
        if has_trial_credits:
            query = query.filter(
                models.user.Subscriber.trial_credits > 0,
                models.user.Subscriber.trial_credits_expires_at > func.now(),
            )
        else:
            query = query.filter(
                or_(
                    models.user.Subscriber.trial_credits == 0,
                    models.user.Subscriber.trial_credits_expires_at <= func.now(),
                )
            )

    if user_role:
        query = query.filter(models.user.User.role == user_role)

    # Search
    if search:
        search_term = f"%{search}%"
        query = query.outerjoin(
            models.user.Contractor,
            models.user.Contractor.user_id == models.user.User.id,
        ).outerjoin(
            models.user.Supplier, models.user.Supplier.user_id == models.user.User.id
        )
        query = query.filter(
            or_(
                models.user.User.email.ilike(search_term),
                models.user.Contractor.primary_contact_name.ilike(search_term),
                models.user.Supplier.primary_contact_name.ilike(search_term),
            )
        )

    # Get total count
    total_count = query.count()

    # Apply pagination
    offset = (page - 1) * per_page
    results = query.offset(offset).limit(per_page).all()

    # Build response data
    data = []
    for user, subscriber, subscription in results:
        # Get user name from contractor or supplier
        contractor = (
            db.query(models.user.Contractor)
            .filter(models.user.Contractor.user_id == user.id)
            .first()
        )
        supplier = (
            db.query(models.user.Supplier)
            .filter(models.user.Supplier.user_id == user.id)
            .first()
        )

        user_name = None
        if contractor:
            user_name = contractor.primary_contact_name
        elif supplier:
            user_name = supplier.primary_contact_name

        # Calculate add-on credits
        addon_credits = 0
        total_addon_credits = 0
        if subscriber:
            addon_credits = (
                (subscriber.stay_active_credits or 0)
                + (subscriber.bonus_credits or 0)
                + (subscriber.boost_pack_credits or 0)
            )
            total_addon_credits = addon_credits  # Same for now

        # Build row data with ALL available fields
        row = {
            # Unique Identifiers
            "id": subscriber.id if subscriber else None,
            "user_id": user.id,
            "user_email": user.email,
            "user_name": user_name,
            "user_role": user.role,
            # Core Credit & Spending Fields
            "current_credits": subscriber.current_credits if subscriber else 0,
            "total_spending": subscriber.total_spending if subscriber else 0,
            "trial_credits": subscriber.trial_credits if subscriber else 0,
            "trial_credits_expires_at": (
                subscriber.trial_credits_expires_at.isoformat()
                if subscriber and subscriber.trial_credits_expires_at
                else None
            ),
            "trial_credits_used": (
                subscriber.trial_credits_used if subscriber else False
            ),
            "frozen_credits": subscriber.frozen_credits if subscriber else 0,
            "frozen_at": (
                subscriber.frozen_at.isoformat()
                if subscriber and subscriber.frozen_at
                else None
            ),
            # Activity & Expiration Metrics
            "last_active_date": (
                subscriber.last_active_date.isoformat()
                if subscriber and subscriber.last_active_date
                else None
            ),
            "stay_active_credits": subscriber.stay_active_credits if subscriber else 0,
            "bonus_credits": subscriber.bonus_credits if subscriber else 0,
            "boost_pack_credits": subscriber.boost_pack_credits if subscriber else 0,
            "boost_pack_seats": subscriber.boost_pack_seats if subscriber else 0,
            "last_stay_active_redemption": (
                subscriber.last_stay_active_redemption.isoformat()
                if subscriber and subscriber.last_stay_active_redemption
                else None
            ),
            "last_bonus_redemption": (
                subscriber.last_bonus_redemption.isoformat()
                if subscriber and subscriber.last_bonus_redemption
                else None
            ),
            "last_boost_redemption": (
                subscriber.last_boost_redemption.isoformat()
                if subscriber and subscriber.last_boost_redemption
                else None
            ),
            # Subscription Details
            "subscription_id": subscriber.subscription_id if subscriber else None,
            "subscription_plan": subscription.name if subscription else None,
            "subscription_status": (
                subscriber.subscription_status if subscriber else "inactive"
            ),
            "subscription_start_date": (
                subscriber.subscription_start_date.isoformat()
                if subscriber and subscriber.subscription_start_date
                else None
            ),
            "subscription_renew_date": (
                subscriber.subscription_renew_date.isoformat()
                if subscriber and subscriber.subscription_renew_date
                else None
            ),
            "is_active": subscriber.is_active if subscriber else False,
            "auto_renew": subscriber.auto_renew if subscriber else True,
            "stripe_subscription_id": (
                subscriber.stripe_subscription_id if subscriber else None
            ),
            # Seats Management
            "seats_used": subscriber.seats_used if subscriber else 0,
            "purchased_seats": subscriber.purchased_seats if subscriber else 0,
            # Cumulative Add-on Credits
            "addon_credits_total": total_addon_credits,
            # First Subscription Tracking
            "first_starter_subscription_at": (
                subscriber.first_starter_subscription_at.isoformat()
                if subscriber and subscriber.first_starter_subscription_at
                else None
            ),
            "first_professional_subscription_at": (
                subscriber.first_professional_subscription_at.isoformat()
                if subscriber and subscriber.first_professional_subscription_at
                else None
            ),
            "first_enterprise_subscription_at": (
                subscriber.first_enterprise_subscription_at.isoformat()
                if subscriber and subscriber.first_enterprise_subscription_at
                else None
            ),
            "first_custom_subscription_at": (
                subscriber.first_custom_subscription_at.isoformat()
                if subscriber and subscriber.first_custom_subscription_at
                else None
            ),
        }

        data.append(row)

    # Calculate pagination
    total_pages = (total_count + per_page - 1) // per_page

    return {
        "data": data,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_items": total_count,
            "total_pages": total_pages,
        },
    }


# Pydantic schema for credits ledger update
class CreditsLedgerUpdate(BaseModel):
    # Core Credit & Spending Fields
    current_credits: Optional[int] = None
    total_spending: Optional[int] = None
    trial_credits: Optional[int] = None
    trial_credits_expires_at: Optional[str] = None  # ISO format datetime string
    trial_credits_used: Optional[bool] = None
    frozen_credits: Optional[int] = None
    frozen_at: Optional[str] = None  # ISO format datetime string

    # Activity & Expiration Metrics
    last_active_date: Optional[str] = None  # ISO format datetime string
    stay_active_credits: Optional[int] = None
    bonus_credits: Optional[int] = None
    boost_pack_credits: Optional[int] = None
    boost_pack_seats: Optional[int] = None
    last_stay_active_redemption: Optional[str] = None  # ISO format datetime string
    last_bonus_redemption: Optional[str] = None  # ISO format datetime string
    last_boost_redemption: Optional[str] = None  # ISO format datetime string

    # Subscription Details
    subscription_plan_id: Optional[int] = None  # Subscription ID (not name)
    subscription_status: Optional[str] = None
    subscription_start_date: Optional[str] = None  # ISO format datetime string
    subscription_renew_date: Optional[str] = None  # ISO format datetime string
    is_active: Optional[bool] = None
    auto_renew: Optional[bool] = None
    stripe_subscription_id: Optional[str] = None

    # Seats Management
    seats_used: Optional[int] = None
    purchased_seats: Optional[int] = None

    # First Subscription Tracking
    first_starter_subscription_at: Optional[str] = None  # ISO format datetime string
    first_professional_subscription_at: Optional[str] = (
        None  # ISO format datetime string
    )
    first_enterprise_subscription_at: Optional[str] = None  # ISO format datetime string
    first_custom_subscription_at: Optional[str] = None  # ISO format datetime string


@router.patch("/credits-ledger/{user_id}", dependencies=[Depends(require_admin_token)])
def update_credits_ledger(
    user_id: int,
    data: CreditsLedgerUpdate = Body(...),
    db: Session = Depends(get_db),
):
    """
    Admin endpoint: Update credit ledger for a specific user.

    All fields from the Subscriber model can be updated EXCEPT:
    - user_id (read-only, specified in path)
    - user_role (cannot change via this endpoint, use user management endpoints)
    - id (auto-generated)

    Editable fields:
    - Core Credit & Spending: current_credits, total_spending, trial_credits, trial_credits_expires_at,
      trial_credits_used, frozen_credits, frozen_at
    - Activity Metrics: last_active_date, stay_active_credits, bonus_credits, boost_pack_credits,
      boost_pack_seats, last_stay_active_redemption, last_bonus_redemption, last_boost_redemption
    - Subscription Details: subscription_plan_id, subscription_status, subscription_start_date,
       subscription_renew_date, is_active, auto_renew, stripe_subscription_id
    - Seats: seats_used, purchased_seats
    - First Subscription Tracking: first_starter_subscription_at, first_professional_subscription_at,
      first_enterprise_subscription_at, first_custom_subscription_at

    All datetime fields accept ISO format strings (YYYY-MM-DDTHH:MM:SS)
    """

    # Find user
    user = db.query(models.user.User).filter(models.user.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with ID {user_id} not found")

    # Find subscriber
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.user_id == user_id)
        .first()
    )

    if not subscriber:
        raise HTTPException(
            status_code=404,
            detail=f"Subscriber record not found for user {user_id}. User must have a subscription first.",
        )

    # Update fields
    updated_fields = []

    # Helper function to parse datetime strings
    def parse_datetime(date_str: str, field_name: str):
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {field_name} format. Use ISO format (YYYY-MM-DDTHH:MM:SS)",
            )

    # Core Credit & Spending Fields
    if data.current_credits is not None:
        subscriber.current_credits = data.current_credits
        updated_fields.append(f"current_credits={data.current_credits}")

    if data.total_spending is not None:
        subscriber.total_spending = data.total_spending
        updated_fields.append(f"total_spending={data.total_spending}")

    if data.trial_credits is not None:
        subscriber.trial_credits = data.trial_credits
        updated_fields.append(f"trial_credits={data.trial_credits}")

    if data.trial_credits_expires_at is not None:
        subscriber.trial_credits_expires_at = parse_datetime(
            data.trial_credits_expires_at, "trial_credits_expires_at"
        )
        updated_fields.append(
            f"trial_credits_expires_at={subscriber.trial_credits_expires_at}"
        )

    if data.trial_credits_used is not None:
        subscriber.trial_credits_used = data.trial_credits_used
        updated_fields.append(f"trial_credits_used={data.trial_credits_used}")

    if data.frozen_credits is not None:
        subscriber.frozen_credits = data.frozen_credits
        updated_fields.append(f"frozen_credits={data.frozen_credits}")

    if data.frozen_at is not None:
        subscriber.frozen_at = parse_datetime(data.frozen_at, "frozen_at")
        updated_fields.append(f"frozen_at={subscriber.frozen_at}")

    # Activity & Expiration Metrics
    if data.last_active_date is not None:
        subscriber.last_active_date = parse_datetime(
            data.last_active_date, "last_active_date"
        )
        updated_fields.append(f"last_active_date={subscriber.last_active_date}")

    if data.stay_active_credits is not None:
        subscriber.stay_active_credits = data.stay_active_credits
        updated_fields.append(f"stay_active_credits={data.stay_active_credits}")

    if data.bonus_credits is not None:
        subscriber.bonus_credits = data.bonus_credits
        updated_fields.append(f"bonus_credits={data.bonus_credits}")

    if data.boost_pack_credits is not None:
        subscriber.boost_pack_credits = data.boost_pack_credits
        updated_fields.append(f"boost_pack_credits={data.boost_pack_credits}")

    if data.boost_pack_seats is not None:
        subscriber.boost_pack_seats = data.boost_pack_seats
        updated_fields.append(f"boost_pack_seats={data.boost_pack_seats}")

    if data.last_stay_active_redemption is not None:
        subscriber.last_stay_active_redemption = parse_datetime(
            data.last_stay_active_redemption, "last_stay_active_redemption"
        )
        updated_fields.append(
            f"last_stay_active_redemption={subscriber.last_stay_active_redemption}"
        )

    if data.last_bonus_redemption is not None:
        subscriber.last_bonus_redemption = parse_datetime(
            data.last_bonus_redemption, "last_bonus_redemption"
        )
        updated_fields.append(
            f"last_bonus_redemption={subscriber.last_bonus_redemption}"
        )

    if data.last_boost_redemption is not None:
        subscriber.last_boost_redemption = parse_datetime(
            data.last_boost_redemption, "last_boost_redemption"
        )
        updated_fields.append(
            f"last_boost_redemption={subscriber.last_boost_redemption}"
        )

    # Subscription Details
    if data.subscription_plan_id is not None:
        # Verify subscription plan exists
        plan = (
            db.query(models.user.Subscription)
            .filter(models.user.Subscription.id == data.subscription_plan_id)
            .first()
        )
        if not plan:
            raise HTTPException(
                status_code=404,
                detail=f"Subscription plan with ID {data.subscription_plan_id} not found",
            )
        subscriber.subscription_id = data.subscription_plan_id
        updated_fields.append(f"subscription_plan={plan.name}")

    if data.subscription_status is not None:
        subscriber.subscription_status = data.subscription_status
        updated_fields.append(f"subscription_status={data.subscription_status}")

    if data.subscription_start_date is not None:
        subscriber.subscription_start_date = parse_datetime(
            data.subscription_start_date, "subscription_start_date"
        )
        updated_fields.append(
            f"subscription_start_date={subscriber.subscription_start_date}"
        )

    if data.subscription_renew_date is not None:
        subscriber.subscription_renew_date = parse_datetime(
            data.subscription_renew_date, "subscription_renew_date"
        )
        updated_fields.append(
            f"subscription_renew_date={subscriber.subscription_renew_date}"
        )

    if data.is_active is not None:
        subscriber.is_active = data.is_active
        updated_fields.append(f"is_active={data.is_active}")

    if data.auto_renew is not None:
        subscriber.auto_renew = data.auto_renew
        updated_fields.append(f"auto_renew={data.auto_renew}")

    if data.stripe_subscription_id is not None:
        subscriber.stripe_subscription_id = data.stripe_subscription_id
        updated_fields.append(f"stripe_subscription_id={data.stripe_subscription_id}")

    # Seats Management
    if data.seats_used is not None:
        subscriber.seats_used = data.seats_used
        updated_fields.append(f"seats_used={data.seats_used}")

    if data.purchased_seats is not None:
        subscriber.purchased_seats = data.purchased_seats
        updated_fields.append(f"purchased_seats={data.purchased_seats}")

    # First Subscription Tracking
    if data.first_starter_subscription_at is not None:
        subscriber.first_starter_subscription_at = parse_datetime(
            data.first_starter_subscription_at, "first_starter_subscription_at"
        )
        updated_fields.append(
            f"first_starter_subscription_at={subscriber.first_starter_subscription_at}"
        )

    if data.first_professional_subscription_at is not None:
        subscriber.first_professional_subscription_at = parse_datetime(
            data.first_professional_subscription_at,
            "first_professional_subscription_at",
        )
        updated_fields.append(
            f"first_professional_subscription_at={subscriber.first_professional_subscription_at}"
        )

    if data.first_enterprise_subscription_at is not None:
        subscriber.first_enterprise_subscription_at = parse_datetime(
            data.first_enterprise_subscription_at, "first_enterprise_subscription_at"
        )
        updated_fields.append(
            f"first_enterprise_subscription_at={subscriber.first_enterprise_subscription_at}"
        )

    if data.first_custom_subscription_at is not None:
        subscriber.first_custom_subscription_at = parse_datetime(
            data.first_custom_subscription_at, "first_custom_subscription_at"
        )
        updated_fields.append(
            f"first_custom_subscription_at={subscriber.first_custom_subscription_at}"
        )

    # Commit changes
    try:
        db.commit()
        db.refresh(subscriber)

        logger.info(
            f"Admin updated credits ledger for user {user_id} ({user.email}): {', '.join(updated_fields)}"
        )

        return {
            "success": True,
            "message": f"Updated {len(updated_fields)} field(s) for user {user.email}",
            "updated_fields": updated_fields,
            "user_id": user_id,
            "user_email": user.email,
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error updating credits ledger for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update credits ledger: {str(e)}"
        )


@router.get("/subscriptions-list", dependencies=[Depends(require_admin_token)])
def subscriptions_list(
    # Pagination
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    # Filters
    subscription_status: Optional[str] = Query(
        None, description="Filter by status: active, canceled, past_due, trialing, etc."
    ),
    plan_name: Optional[str] = Query(
        None, description="Filter by plan: Starter, Professional, Enterprise, Custom"
    ),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    auto_renew: Optional[bool] = Query(
        None, description="Filter by auto-renew enabled/disabled"
    ),
    has_stripe_id: Optional[bool] = Query(
        None, description="Filter subscriptions with/without Stripe ID"
    ),
    user_role: Optional[str] = Query(
        None, description="Filter by user role: Contractor, Supplier"
    ),
    # Date filters
    created_after: Optional[str] = Query(
        None, description="Filter created after date (YYYY-MM-DD)"
    ),
    renews_before: Optional[str] = Query(
        None, description="Filter renews before date (YYYY-MM-DD)"
    ),
    # Search
    search: Optional[str] = Query(
        None, description="Search by email, name, or Stripe ID"
    ),
    db: Session = Depends(get_db),
):
    """
    Admin endpoint: Get comprehensive subscriptions list.

    Returns all subscription records with complete details:
    - User information (id, email, name, role, created_at)
    - Subscription plan details (name, price, credits, seats)
    - Stripe information (subscription_id, price_id, product_id)
    - Status & billing (status, is_active, auto_renew, start/renew dates)
    - Credits & spending summary
    - Seats usage

    Perfect for subscription management, billing oversight, and customer support.
    """

    # Base query
    query = (
        db.query(
            models.user.User,
            models.user.Subscriber,
            models.user.Subscription,
        )
        .join(
            models.user.Subscriber,
            models.user.Subscriber.user_id == models.user.User.id,
        )
        .outerjoin(
            models.user.Subscription,
            models.user.Subscriber.subscription_id == models.user.Subscription.id,
        )
        .filter(models.user.User.approved_by_admin == "approved")
    )

    # Apply filters
    if subscription_status:
        query = query.filter(
            models.user.Subscriber.subscription_status == subscription_status
        )

    if plan_name:
        query = query.filter(models.user.Subscription.name == plan_name)

    if is_active is not None:
        query = query.filter(models.user.Subscriber.is_active == is_active)

    if auto_renew is not None:
        query = query.filter(models.user.Subscriber.auto_renew == auto_renew)

    if has_stripe_id is not None:
        if has_stripe_id:
            query = query.filter(models.user.Subscriber.stripe_subscription_id != None)
        else:
            query = query.filter(models.user.Subscriber.stripe_subscription_id == None)

    if user_role:
        query = query.filter(models.user.User.role == user_role)

    # Date filters
    if created_after:
        try:
            created_date = datetime.strptime(created_after, "%Y-%m-%d")
            query = query.filter(models.user.User.created_at >= created_date)
        except ValueError:
            pass  # Invalid date format, skip filter

    if renews_before:
        try:
            renew_date = datetime.strptime(renews_before, "%Y-%m-%d")
            query = query.filter(
                models.user.Subscriber.subscription_renew_date <= renew_date
            )
        except ValueError:
            pass  # Invalid date format, skip filter

    # Search
    if search:
        search_term = f"%{search}%"
        query = query.outerjoin(
            models.user.Contractor,
            models.user.Contractor.user_id == models.user.User.id,
        ).outerjoin(
            models.user.Supplier, models.user.Supplier.user_id == models.user.User.id
        )
        query = query.filter(
            or_(
                models.user.User.email.ilike(search_term),
                models.user.Contractor.primary_contact_name.ilike(search_term),
                models.user.Supplier.primary_contact_name.ilike(search_term),
                models.user.Subscriber.stripe_subscription_id.ilike(search_term),
                func.cast(models.user.User.id, String).ilike(search_term),
            )
        )

    # Get total count
    total_count = query.count()

    # Apply pagination and ordering (most recent first)
    offset = (page - 1) * per_page
    results = (
        query.order_by(models.user.Subscriber.subscription_start_date.desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )

    # Build response data
    data = []
    for user, subscriber, subscription in results:
        # Get user name from contractor or supplier
        contractor = (
            db.query(models.user.Contractor)
            .filter(models.user.Contractor.user_id == user.id)
            .first()
        )
        supplier = (
            db.query(models.user.Supplier)
            .filter(models.user.Supplier.user_id == user.id)
            .first()
        )

        user_name = None
        company_name = None
        if contractor:
            user_name = contractor.primary_contact_name
            company_name = contractor.company_name
        elif supplier:
            user_name = supplier.primary_contact_name
            company_name = supplier.company_name

        # Build comprehensive subscription row
        row = {
            # User Information
            "user_id": user.id,
            "user_email": user.email,
            "user_name": user_name,
            "company_name": company_name,
            "user_role": user.role,
            "user_created_at": user.created_at.isoformat() if user.created_at else None,
            # Subscriber/Subscription IDs
            "subscriber_id": subscriber.id,
            "subscription_id": subscriber.subscription_id,
            # Stripe Information
            "stripe_subscription_id": subscriber.stripe_subscription_id,
            "stripe_price_id": subscription.stripe_price_id if subscription else None,
            "stripe_product_id": (
                subscription.stripe_product_id if subscription else None
            ),
            # Subscription Plan Details
            "plan_name": subscription.name if subscription else None,
            "plan_price": subscription.price if subscription else None,
            "plan_credits": subscription.credits if subscription else None,
            "plan_max_seats": subscription.max_seats if subscription else None,
            "plan_tier_level": subscription.tier_level if subscription else None,
            # For Custom plan
            "plan_credit_price": subscription.credit_price if subscription else None,
            "plan_seat_price": subscription.seat_price if subscription else None,
            # Subscription Status & Dates
            "subscription_status": subscriber.subscription_status,
            "is_active": subscriber.is_active,
            "auto_renew": subscriber.auto_renew,
            "subscription_start_date": (
                subscriber.subscription_start_date.isoformat()
                if subscriber.subscription_start_date
                else None
            ),
            "subscription_renew_date": (
                subscriber.subscription_renew_date.isoformat()
                if subscriber.subscription_renew_date
                else None
            ),
            "last_active_date": (
                subscriber.last_active_date.isoformat()
                if subscriber.last_active_date
                else None
            ),
            # Credits Summary (for context)
            "current_credits": subscriber.current_credits,
            "total_spending": subscriber.total_spending,
            "frozen_credits": subscriber.frozen_credits,
            "frozen_at": (
                subscriber.frozen_at.isoformat() if subscriber.frozen_at else None
            ),
            # Trial Information
            "trial_credits": subscriber.trial_credits,
            "trial_credits_expires_at": (
                subscriber.trial_credits_expires_at.isoformat()
                if subscriber.trial_credits_expires_at
                else None
            ),
            "trial_credits_used": subscriber.trial_credits_used,
            # Seats Management
            "seats_used": subscriber.seats_used,
            "purchased_seats": subscriber.purchased_seats,
            # Add-on Credits (for context)
            "stay_active_credits": subscriber.stay_active_credits,
            "bonus_credits": subscriber.bonus_credits,
            "boost_pack_credits": subscriber.boost_pack_credits,
            "boost_pack_seats": subscriber.boost_pack_seats,
            # First Subscription Tracking
            "first_starter_subscription_at": (
                subscriber.first_starter_subscription_at.isoformat()
                if subscriber.first_starter_subscription_at
                else None
            ),
            "first_professional_subscription_at": (
                subscriber.first_professional_subscription_at.isoformat()
                if subscriber.first_professional_subscription_at
                else None
            ),
            "first_enterprise_subscription_at": (
                subscriber.first_enterprise_subscription_at.isoformat()
                if subscriber.first_enterprise_subscription_at
                else None
            ),
            "first_custom_subscription_at": (
                subscriber.first_custom_subscription_at.isoformat()
                if subscriber.first_custom_subscription_at
                else None
            ),
        }

        data.append(row)

    # Calculate pagination
    total_pages = (total_count + per_page - 1) // per_page

    return {
        "data": data,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_items": total_count,
            "total_pages": total_pages,
        },
    }


@router.get("/payments", dependencies=[Depends(require_admin_token)])
def get_payments(
    # Pagination
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    # Filters
    subscription_status: Optional[str] = Query(
        None, description="Filter by subscription status"
    ),
    plan_name: Optional[str] = Query(
        None, description="Filter by plan: Starter, Professional, Enterprise, Custom"
    ),
    user_role: Optional[str] = Query(
        None, description="Filter by user role: Contractor, Supplier"
    ),
    # Date filters
    payment_after: Optional[str] = Query(
        None, description="Filter payments after date (YYYY-MM-DD)"
    ),
    payment_before: Optional[str] = Query(
        None, description="Filter payments before date (YYYY-MM-DD)"
    ),
    # Search
    search: Optional[str] = Query(
        None, description="Search by email, name, or Stripe ID"
    ),
    db: Session = Depends(get_db),
):
    """
    Admin endpoint: Get comprehensive payments list.

    Returns payment history for all subscribers by fetching Stripe invoice data.
    Each row represents a successful payment with:
    - User information (email, name, role)
    - Subscription details (plan, status, dates)
    - Payment information (invoice ID, amount, date, billing address)
    - Stripe IDs (subscription_id, customer_id)

    Note: This makes Stripe API calls so may take a few seconds for large result sets.
    """

    # Base query for subscribers
    query = (
        db.query(
            models.user.User,
            models.user.Subscriber,
            models.user.Subscription,
        )
        .join(
            models.user.Subscriber,
            models.user.Subscriber.user_id == models.user.User.id,
        )
        .outerjoin(
            models.user.Subscription,
            models.user.Subscriber.subscription_id == models.user.Subscription.id,
        )
        .filter(
            models.user.User.approved_by_admin == "approved",
            models.user.User.stripe_customer_id
            != None,  # Only users with Stripe customers
        )
    )

    # Apply filters
    if subscription_status:
        query = query.filter(
            models.user.Subscriber.subscription_status == subscription_status
        )

    if plan_name:
        query = query.filter(models.user.Subscription.name == plan_name)

    if user_role:
        query = query.filter(models.user.User.role == user_role)

    # Search
    if search:
        search_term = f"%{search}%"
        query = query.outerjoin(
            models.user.Contractor,
            models.user.Contractor.user_id == models.user.User.id,
        ).outerjoin(
            models.user.Supplier, models.user.Supplier.user_id == models.user.User.id
        )
        query = query.filter(
            or_(
                models.user.User.email.ilike(search_term),
                models.user.Contractor.primary_contact_name.ilike(search_term),
                models.user.Supplier.primary_contact_name.ilike(search_term),
                models.user.Subscriber.stripe_subscription_id.ilike(search_term),
                models.user.User.stripe_customer_id.ilike(search_term),
            )
        )

    # Get all matching subscribers (we'll paginate the payments, not the subscribers)
    subscribers = query.all()

    # Build payments list by fetching Stripe invoices
    all_payments = []

    for user, subscriber, subscription in subscribers:
        # Get user name
        contractor = (
            db.query(models.user.Contractor)
            .filter(models.user.Contractor.user_id == user.id)
            .first()
        )
        supplier = (
            db.query(models.user.Supplier)
            .filter(models.user.Supplier.user_id == user.id)
            .first()
        )

        user_name = None
        company_name = None
        billing_address = None

        if contractor:
            user_name = contractor.primary_contact_name
            company_name = contractor.company_name
        elif supplier:
            user_name = supplier.primary_contact_name
            company_name = supplier.company_name

        # Fetch Stripe invoices for this customer
        try:
            invoices = stripe.Invoice.list(
                customer=user.stripe_customer_id,
                limit=100,  # Last 100 invoices per customer
                expand=["data.customer_address"],
            )

            for invoice in invoices.data:
                # Only include paid invoices
                if invoice.status != "paid":
                    continue

                payment_date = datetime.fromtimestamp(invoice.created)

                # Apply date filters
                if payment_after:
                    try:
                        filter_date = datetime.strptime(payment_after, "%Y-%m-%d")
                        if payment_date < filter_date:
                            continue
                    except ValueError:
                        pass

                if payment_before:
                    try:
                        filter_date = datetime.strptime(payment_before, "%Y-%m-%d")
                        if payment_date > filter_date:
                            continue
                    except ValueError:
                        pass

                # Get billing address from invoice or customer
                billing_address = None
                if hasattr(invoice, "customer_address") and invoice.customer_address:
                    addr = invoice.customer_address
                    address_parts = []
                    if addr.get("line1"):
                        address_parts.append(addr["line1"])
                    if addr.get("city"):
                        address_parts.append(addr["city"])
                    if addr.get("state"):
                        address_parts.append(addr["state"])
                    if addr.get("postal_code"):
                        address_parts.append(addr["postal_code"])
                    if address_parts:
                        billing_address = ", ".join(address_parts)

                # If no address from invoice, try to get from customer
                if not billing_address and company_name:
                    billing_address = company_name

                all_payments.append(
                    {
                        # Stripe IDs
                        "stripe_subscription_id": (
                            subscriber.stripe_subscription_id if subscriber else None
                        ),
                        "stripe_customer_id": user.stripe_customer_id,
                        "stripe_invoice_id": invoice.id,
                        # User Information
                        "user_id": user.id,
                        "user_email": user.email,
                        "user_name": user_name,
                        "company_name": company_name,
                        "user_role": user.role,
                        "user_created_at": (
                            user.created_at.isoformat() if user.created_at else None
                        ),
                        # Subscription Details
                        "subscription_id": (
                            subscriber.subscription_id if subscriber else None
                        ),
                        "subscription_plan": (
                            subscription.name if subscription else None
                        ),
                        "subscription_status": (
                            subscriber.subscription_status if subscriber else None
                        ),
                        "subscription_renew_date": (
                            subscriber.subscription_renew_date.isoformat()
                            if subscriber and subscriber.subscription_renew_date
                            else None
                        ),
                        # Payment Details
                        "amount_paid": invoice.amount_paid
                        / 100.0,  # Convert cents to dollars
                        "currency": (
                            invoice.currency.upper() if invoice.currency else "USD"
                        ),
                        "payment_date": payment_date.isoformat(),
                        "invoice_number": invoice.number,
                        "invoice_status": invoice.status,
                        "billing_address": billing_address,
                        # Payment timestamp for sorting
                        "_payment_timestamp": invoice.created,
                    }
                )

        except Exception as e:
            logger.error(
                f"Error fetching invoices for customer {user.stripe_customer_id}: {str(e)}"
            )
            continue

    # Sort all payments by payment date (newest first)
    all_payments.sort(key=lambda x: x["_payment_timestamp"], reverse=True)

    # Remove the sorting helper field
    for payment in all_payments:
        del payment["_payment_timestamp"]

    # Apply pagination to the combined payments list
    total_count = len(all_payments)
    total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 0

    offset = (page - 1) * per_page
    paginated_payments = all_payments[offset : offset + per_page]

    return {
        "data": paginated_payments,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_items": total_count,
            "total_pages": total_pages,
        },
    }
