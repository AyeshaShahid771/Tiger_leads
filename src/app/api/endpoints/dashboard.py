import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from src.app import models, schemas
from src.app.api.deps import get_current_user
from src.app.core.database import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", response_model=schemas.subscription.DashboardResponse)
def get_dashboard(
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    """
    Get dashboard information for the authenticated user.
    Shows different data based on whether user is Contractor or Supplier.
    """
    # Check user role and profile completion
    is_profile_complete = False
    user_profile = None

    if current_user.role == "Contractor":
        contractor = (
            db.query(models.user.Contractor)
            .filter(models.user.Contractor.user_id == current_user.id)
            .first()
        )
        if contractor and contractor.is_completed:
            is_profile_complete = True
            user_profile = contractor
    elif current_user.role == "Supplier":
        supplier = (
            db.query(models.user.Supplier)
            .filter(models.user.Supplier.user_id == current_user.id)
            .first()
        )
        if supplier and supplier.is_completed:
            is_profile_complete = True
            user_profile = supplier
    else:
        raise HTTPException(
            status_code=403,
            detail="User must be a Contractor or Supplier to access dashboard",
        )

    if not is_profile_complete:
        raise HTTPException(
            status_code=403,
            detail="Please complete your profile to access the dashboard",
        )

    # Get subscriber information
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.user_id == current_user.id)
        .first()
    )

    credit_balance = 0
    credits_added_this_week = 0
    active_subscription = None
    subscription_renew_date = None

    if subscriber:
        credit_balance = subscriber.current_credits

        # Get subscription name
        if subscriber.subscription_id:
            subscription = (
                db.query(models.user.Subscription)
                .filter(models.user.Subscription.id == subscriber.subscription_id)
                .first()
            )
            if subscription:
                active_subscription = subscription.name

        subscription_renew_date = subscriber.subscription_renew_date

        # Calculate credits added this week
        week_ago = datetime.now() - timedelta(days=7)
        if (
            subscriber.subscription_start_date
            and subscriber.subscription_start_date >= week_ago
        ):
            if subscriber.subscription_id:
                subscription = (
                    db.query(models.user.Subscription)
                    .filter(models.user.Subscription.id == subscriber.subscription_id)
                    .first()
                )
                if subscription:
                    credits_added_this_week = subscription.tokens

    # Get total jobs unlocked
    total_jobs_unlocked = (
        db.query(models.user.UnlockedLead)
        .filter(models.user.UnlockedLead.user_id == current_user.id)
        .count()
    )

    # Build query for available jobs based on user profile
    jobs_query = db.query(models.user.Job)

    if current_user.role == "Contractor":
        filter_conditions = []
        if user_profile.state:
            filter_conditions.append(models.user.Job.state == user_profile.state)
        if user_profile.work_type:
            filter_conditions.append(
                models.user.Job.work_type == user_profile.work_type
            )
        # Filter by contractor's business types (multiple categories)
        if user_profile.business_types:
            business_types = json.loads(user_profile.business_types)
            filter_conditions.append(models.user.Job.category.in_(business_types))
        if filter_conditions:
            jobs_query = jobs_query.filter(and_(*filter_conditions))

    elif current_user.role == "Supplier":
        filter_conditions = []
        if user_profile.service_states:
            service_states = json.loads(user_profile.service_states)
            filter_conditions.append(models.user.Job.state.in_(service_states))
        # Filter by supplier's product categories
        if user_profile.product_categories:
            product_categories = json.loads(user_profile.product_categories)
            filter_conditions.append(models.user.Job.category.in_(product_categories))
        if filter_conditions:
            jobs_query = jobs_query.filter(and_(*filter_conditions))

    # Get total available jobs
    total_available_jobs = jobs_query.count()

    # Get paginated recent leads
    offset = (page - 1) * page_size
    recent_jobs = (
        jobs_query.order_by(models.user.Job.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    # Convert to response format (hide sensitive data for locked leads)
    recent_leads = [
        {
            "id": job.id,
            "permit_record_number": job.permit_record_number,
            "date": job.date,
            "permit_type": job.permit_type,
            "project_description": job.project_description,
            "job_address": job.job_address,
            "job_cost": job.job_cost,
            "permit_status": job.permit_status,
            "country": job.country,
            "city": job.city,
            "state": job.state,
            "work_type": job.work_type,
            "credit_cost": job.credit_cost,
            "category": job.category,
            "created_at": job.created_at,
        }
        for job in recent_jobs
    ]

    total_pages = (total_available_jobs + page_size - 1) // page_size

    return {
        "user_email": current_user.email,
        "role": current_user.role,
        "is_profile_complete": is_profile_complete,
        "credit_balance": credit_balance,
        "credits_added_this_week": credits_added_this_week,
        "active_subscription": active_subscription,
        "subscription_renew_date": subscription_renew_date,
        "total_jobs_unlocked": total_jobs_unlocked,
        "total_available_jobs": total_available_jobs,
        "recent_leads": recent_leads,
        "current_page": page,
        "total_pages": total_pages,
    }
