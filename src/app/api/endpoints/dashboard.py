import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from src.app import models, schemas
from src.app.api.deps import get_current_user
from src.app.core.database import get_db
from src.app.data import product_keywords, trade_keywords

# Configure logging to use uvicorn logger
logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", response_model=schemas.subscription.DashboardResponse)
def get_dashboard(
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get dashboard information for the authenticated user.
    Returns:
    - Credit balance
    - Credits added this week
    - Current plan name (Free Plan if balance=0 and spending=0)
    - Renewal date (format: "February 2025")
    - Profile completion month
    - Total jobs unlocked
    - Top 20 matched jobs (id, trs_score, permit_type, country_city, state)
    """
    # Check user role
    if current_user.role not in ["Contractor", "Supplier"]:
        raise HTTPException(
            status_code=403,
            detail="User must be a Contractor or Supplier to access dashboard",
        )

    # Get user profile
    user_profile = None
    profile_completed_at = None

    if current_user.role == "Contractor":
        contractor = (
            db.query(models.user.Contractor)
            .filter(models.user.Contractor.user_id == current_user.id)
            .first()
        )
        if contractor and contractor.is_completed:
            user_profile = contractor
            profile_completed_at = contractor.updated_at or contractor.created_at
    else:  # Supplier
        supplier = (
            db.query(models.user.Supplier)
            .filter(models.user.Supplier.user_id == current_user.id)
            .first()
        )
        if supplier and supplier.is_completed:
            user_profile = supplier
            profile_completed_at = supplier.updated_at or supplier.created_at

    if not user_profile:
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
    plan_name = "Free Plan"
    renewal_date = None

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
                plan_name = subscription.name

                # Format renewal date as "February 2025"
                if subscriber.subscription_renew_date:
                    renewal_date = subscriber.subscription_renew_date.strftime("%B %Y")

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
                    credits_added_this_week = subscription.credits

        # Check if user should have Free Plan (balance=0 and no spending)
        total_spent = (
            db.query(func.sum(models.user.UnlockedLead.credits_spent))
            .filter(models.user.UnlockedLead.user_id == current_user.id)
            .scalar()
            or 0
        )
        if credit_balance == 0 and total_spent == 0:
            plan_name = "Free Plan"
            renewal_date = None

    # Get total jobs unlocked
    total_jobs_unlocked = (
        db.query(models.user.UnlockedLead)
        .filter(models.user.UnlockedLead.user_id == current_user.id)
        .count()
    )

    # Format profile completion month
    profile_completion_month = None
    if profile_completed_at:
        profile_completion_month = profile_completed_at.strftime("%B %Y")

    # Get top 20 matched jobs using same logic as matched-jobs endpoints
    search_conditions = []

    if current_user.role == "Contractor":
        # Get trade category
        trade_category = user_profile.trade_categories
        if trade_category:
            trade_categories = [trade_category.strip()]

            # Build keyword search conditions
            for category in trade_categories:
                keywords = trade_keywords.get_keywords_for_trade(category)
                if keywords:
                    category_conditions = []
                    for keyword in keywords:
                        keyword_pattern = f"%{keyword}%"
                        category_conditions.append(
                            or_(
                                models.user.Job.permit_type.ilike(keyword_pattern),
                                models.user.Job.project_description.ilike(
                                    keyword_pattern
                                ),
                            )
                        )
                    if category_conditions:
                        search_conditions.append(or_(*category_conditions))

        # Location filters
        contractor_states = user_profile.state if user_profile.state else []
        contractor_country_cities = (
            user_profile.country_city if user_profile.country_city else []
        )

    else:  # Supplier
        # Get product category
        product_category = user_profile.product_categories
        if product_category:
            product_categories = [product_category.strip()]

            # Build keyword search conditions
            for category in product_categories:
                keywords = product_keywords.get_keywords_for_product(category)
                if keywords:
                    category_conditions = []
                    for keyword in keywords:
                        keyword_pattern = f"%{keyword}%"
                        category_conditions.append(
                            or_(
                                models.user.Job.permit_type.ilike(keyword_pattern),
                                models.user.Job.project_description.ilike(
                                    keyword_pattern
                                ),
                            )
                        )
                    if category_conditions:
                        search_conditions.append(or_(*category_conditions))

        # Location filters
        contractor_states = (
            user_profile.service_states if user_profile.service_states else []
        )
        contractor_country_cities = (
            user_profile.country_city if user_profile.country_city else []
        )

    # Get list of not-interested job IDs for this user
    not_interested_job_ids = (
        db.query(models.user.NotInterestedJob.job_id)
        .filter(models.user.NotInterestedJob.user_id == current_user.id)
        .all()
    )
    not_interested_ids = [job_id[0] for job_id in not_interested_job_ids]

    # Get list of unlocked job IDs for this user
    unlocked_job_ids = (
        db.query(models.user.UnlockedLead.job_id)
        .filter(models.user.UnlockedLead.user_id == current_user.id)
        .all()
    )
    unlocked_ids = [job_id[0] for job_id in unlocked_job_ids]

    # Combine excluded IDs
    excluded_ids = list(set(not_interested_ids + unlocked_ids))

    # Build base query
    base_query = db.query(models.user.Job)

    if search_conditions:
        base_query = base_query.filter(or_(*search_conditions))

    # Exclude not-interested and unlocked jobs
    if excluded_ids:
        base_query = base_query.filter(~models.user.Job.id.in_(excluded_ids))

    # Filter by states (match ANY state in array)
    if contractor_states and len(contractor_states) > 0:
        state_conditions = [
            models.user.Job.state.ilike(f"%{state}%") for state in contractor_states
        ]
        base_query = base_query.filter(or_(*state_conditions))

    # Filter by country_city (match ANY city/county in array)
    if contractor_country_cities and len(contractor_country_cities) > 0:
        city_conditions = [
            models.user.Job.country_city.ilike(f"%{city}%")
            for city in contractor_country_cities
        ]
        base_query = base_query.filter(or_(*city_conditions))

    # Get top 20 jobs ordered by TRS score
    top_jobs = (
        base_query.order_by(
            models.user.Job.trs_score.desc(), models.user.Job.created_at.desc()
        )
        .limit(20)
        .all()
    )

    # Convert to summary format
    top_matched_jobs = [
        {
            "id": job.id,
            "trs_score": job.trs_score,
            "permit_type": job.permit_type,
            "country_city": job.country_city,
            "state": job.state,
        }
        for job in top_jobs
    ]

    # Log the job IDs being sent to user
    job_ids_sent = [job["id"] for job in top_matched_jobs]
    logger.info(
        f"Dashboard GET - User {current_user.id} ({current_user.role}) - Sending {len(job_ids_sent)} jobs: {job_ids_sent}"
    )

    return {
        "credit_balance": credit_balance,
        "credits_added_this_week": credits_added_this_week,
        "plan_name": plan_name,
        "renewal_date": renewal_date,
        "profile_completion_month": profile_completion_month,
        "total_jobs_unlocked": total_jobs_unlocked,
        "top_matched_jobs": top_matched_jobs,
    }


@router.get(
    "/matched-jobs", response_model=schemas.subscription.SimplifiedMatchedJobsResponse
)
def get_more_matched_jobs(
    exclude_ids: str = Query(
        "", description="Comma-separated list of job IDs already shown to user"
    ),
    limit: int = Query(20, ge=1, le=50, description="Number of jobs to return"),
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get more matched jobs for dashboard pagination.
    Returns simplified job data (id, trs_score, permit_type, country_city, state only).
    Excludes:
    - Jobs already passed in exclude_ids (currently displayed jobs)
    - Jobs user marked as not interested
    - Uses same matching logic as main dashboard
    """
    # Check user role
    if current_user.role not in ["Contractor", "Supplier"]:
        raise HTTPException(
            status_code=403,
            detail="User must be a Contractor or Supplier",
        )

    # Get user profile
    user_profile = None

    if current_user.role == "Contractor":
        contractor = (
            db.query(models.user.Contractor)
            .filter(models.user.Contractor.user_id == current_user.id)
            .first()
        )
        if contractor and contractor.is_completed:
            user_profile = contractor
    else:  # Supplier
        supplier = (
            db.query(models.user.Supplier)
            .filter(models.user.Supplier.user_id == current_user.id)
            .first()
        )
        if supplier and supplier.is_completed:
            user_profile = supplier

    if not user_profile:
        raise HTTPException(
            status_code=403,
            detail="Please complete your profile",
        )

    # Parse exclude_ids from query string
    exclude_job_ids = []
    if exclude_ids:
        try:
            exclude_job_ids = [
                int(id.strip()) for id in exclude_ids.split(",") if id.strip()
            ]
        except:
            pass

    # Get not-interested job IDs
    not_interested_job_ids = (
        db.query(models.user.NotInterestedJob.job_id)
        .filter(models.user.NotInterestedJob.user_id == current_user.id)
        .all()
    )
    not_interested_ids = [job_id[0] for job_id in not_interested_job_ids]

    # Get unlocked job IDs
    unlocked_job_ids = (
        db.query(models.user.UnlockedLead.job_id)
        .filter(models.user.UnlockedLead.user_id == current_user.id)
        .all()
    )
    unlocked_ids = [job_id[0] for job_id in unlocked_job_ids]

    # Combine all IDs to exclude
    all_excluded_ids = list(set(exclude_job_ids + not_interested_ids + unlocked_ids))

    # Build search conditions (same as dashboard)
    search_conditions = []

    if current_user.role == "Contractor":
        trade_category = user_profile.trade_categories
        if trade_category:
            trade_categories = [trade_category.strip()]
            for category in trade_categories:
                keywords = trade_keywords.get_keywords_for_trade(category)
                if keywords:
                    category_conditions = []
                    for keyword in keywords:
                        keyword_pattern = f"%{keyword}%"
                        category_conditions.append(
                            or_(
                                models.user.Job.permit_type.ilike(keyword_pattern),
                                models.user.Job.project_description.ilike(
                                    keyword_pattern
                                ),
                            )
                        )
                    if category_conditions:
                        search_conditions.append(or_(*category_conditions))

        contractor_states = user_profile.state if user_profile.state else []
        contractor_country_cities = (
            user_profile.country_city if user_profile.country_city else []
        )

    else:  # Supplier
        product_category = user_profile.product_categories
        if product_category:
            product_categories = [product_category.strip()]
            for category in product_categories:
                keywords = product_keywords.get_keywords_for_product(category)
                if keywords:
                    category_conditions = []
                    for keyword in keywords:
                        keyword_pattern = f"%{keyword}%"
                        category_conditions.append(
                            or_(
                                models.user.Job.permit_type.ilike(keyword_pattern),
                                models.user.Job.project_description.ilike(
                                    keyword_pattern
                                ),
                            )
                        )
                    if category_conditions:
                        search_conditions.append(or_(*category_conditions))

        contractor_states = (
            user_profile.service_states if user_profile.service_states else []
        )
        contractor_country_cities = (
            user_profile.country_city if user_profile.country_city else []
        )

    # Build query
    base_query = db.query(models.user.Job)

    if search_conditions:
        base_query = base_query.filter(or_(*search_conditions))

    # Exclude already shown and not-interested jobs
    if all_excluded_ids:
        base_query = base_query.filter(~models.user.Job.id.in_(all_excluded_ids))

    # Filter by location
    if contractor_states and len(contractor_states) > 0:
        state_conditions = [
            models.user.Job.state.ilike(f"%{state}%") for state in contractor_states
        ]
        base_query = base_query.filter(or_(*state_conditions))

    if contractor_country_cities and len(contractor_country_cities) > 0:
        city_conditions = [
            models.user.Job.country_city.ilike(f"%{city}%")
            for city in contractor_country_cities
        ]
        base_query = base_query.filter(or_(*city_conditions))

    # Get total count
    total_count = base_query.count()

    # Get jobs ordered by TRS score
    jobs = (
        base_query.order_by(
            models.user.Job.trs_score.desc(), models.user.Job.created_at.desc()
        )
        .limit(limit)
        .all()
    )

    # Convert to simplified response format (same as dashboard top jobs)
    job_responses = [
        schemas.subscription.MatchedJobSummary(
            id=job.id,
            trs_score=job.trs_score,
            permit_type=job.permit_type,
            country_city=job.country_city,
            state=job.state,
        )
        for job in jobs
    ]

    return schemas.subscription.SimplifiedMatchedJobsResponse(
        jobs=job_responses,
        total=total_count,
        page=1,
        page_size=len(job_responses),
        total_pages=1,
    )


@router.post("/mark-not-interested")
def mark_job_not_interested(
    job_id: int,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mark a job as "not interested" so user never sees it again.
    """
    # Check if already marked
    existing = (
        db.query(models.user.NotInterestedJob)
        .filter(
            models.user.NotInterestedJob.user_id == current_user.id,
            models.user.NotInterestedJob.job_id == job_id,
        )
        .first()
    )

    if existing:
        return {"message": "Job already marked as not interested"}

    # Create new entry
    not_interested = models.user.NotInterestedJob(
        user_id=current_user.id,
        job_id=job_id,
    )

    db.add(not_interested)
    db.commit()

    return {"message": "Job marked as not interested", "job_id": job_id}


@router.post("/unlock-job")
def unlock_job(
    job_id: int,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Unlock a job by spending credits.
    - Checks if user has enough credits
    - Deducts TRS score from user's credit balance
    - Returns full job details (email, phone, etc.)
    - Null fields returned as "N/A"
    """
    # Get the job
    job = db.query(models.user.Job).filter(models.user.Job.id == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check if already unlocked
    existing_unlock = (
        db.query(models.user.UnlockedLead)
        .filter(
            models.user.UnlockedLead.user_id == current_user.id,
            models.user.UnlockedLead.job_id == job_id,
        )
        .first()
    )

    if existing_unlock:
        # Already unlocked, just return the data
        return {
            "message": "Job already unlocked",
            "job": {
                "id": job.id,
                "permit_type": job.permit_type or "N/A",
                "job_cost": job.job_cost or "N/A",
                "job_address": job.job_address or "N/A",
                "trs_score": job.trs_score or "N/A",
                "email": job.email or "N/A",
                "phone_number": job.phone_number or "N/A",
                "country_city": job.country_city or "N/A",
                "state": job.state or "N/A",
                "project_description": job.project_description or "N/A",
            },
        }

    # Get subscriber info
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.user_id == current_user.id)
        .first()
    )

    if not subscriber:
        raise HTTPException(
            status_code=403,
            detail="You must have an active subscription to unlock jobs",
        )

    # Use TRS score as credit cost (or job.credit_cost if available)
    credits_needed = job.trs_score if job.trs_score else job.credit_cost or 1

    # Check if user has enough credits
    if subscriber.current_credits < credits_needed:
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient credits. You need {credits_needed} credits but only have {subscriber.current_credits}",
        )

    # Deduct credits
    subscriber.current_credits -= credits_needed

    # Create unlocked lead record
    unlocked_lead = models.user.UnlockedLead(
        user_id=current_user.id,
        job_id=job_id,
        credits_spent=credits_needed,
    )

    db.add(unlocked_lead)
    db.commit()
    db.refresh(subscriber)

    return {
        "message": "Job unlocked successfully",
        "credits_spent": credits_needed,
        "remaining_credits": subscriber.current_credits,
        "job": {
            "id": job.id,
            "permit_type": job.permit_type or "N/A",
            "job_cost": job.job_cost or "N/A",
            "job_address": job.job_address or "N/A",
            "trs_score": job.trs_score or "N/A",
            "email": job.email or "N/A",
            "phone_number": job.phone_number or "N/A",
            "country_city": job.country_city or "N/A",
            "state": job.state or "N/A",
            "project_description": job.project_description or "N/A",
        },
    }
