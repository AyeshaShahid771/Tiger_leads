import json
import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from src.app import models, schemas
from src.app.api.deps import get_current_user, get_effective_user
from src.app.core.database import get_db

# Configure logging to use uvicorn logger
logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.post("/save-job/{job_id}")
def save_job(
    job_id: int,
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Save a job to user's saved jobs list.

    Requires authentication token in header.
    Returns success message if job is saved or already saved.
    """
    logger.info(
        f"Save job request from user {effective_user.email} for job_id: {job_id}"
    )

    # Verify the job exists and is posted
    job = db.query(models.user.Job).filter(
        models.user.Job.id == job_id,
        models.user.Job.job_review_status == 'posted'
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check if already saved
    existing_saved = (
        db.query(models.user.SavedJob)
        .filter(
            models.user.SavedJob.user_id == effective_user.id,
            models.user.SavedJob.job_id == job_id,
        )
        .first()
    )

    if existing_saved:
        return {
            "message": "Job already saved",
            "job_id": job_id,
            "saved_at": existing_saved.saved_at,
        }

    # Create new saved job entry
    saved_job = models.user.SavedJob(user_id=effective_user.id, job_id=job_id)

    db.add(saved_job)
    db.commit()
    db.refresh(saved_job)

    logger.info(f"Job {job_id} saved by user {effective_user.id}")

    return {
        "message": "Job saved successfully",
        "job_id": job_id,
        "saved_at": saved_job.saved_at,
    }


@router.delete("/unsave-job/{job_id}")
def unsave_job(
    job_id: int,
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Remove a job from user's saved jobs list.

    Requires authentication token in header.
    Returns success message if job is removed or was not saved.
    """
    logger.info(
        f"Unsave job request from user {effective_user.email} for job_id: {job_id}"
    )

    # Find and delete the saved job entry
    saved_job = (
        db.query(models.user.SavedJob)
        .filter(
            models.user.SavedJob.user_id == effective_user.id,
            models.user.SavedJob.job_id == job_id,
        )
        .first()
    )

    if not saved_job:
        return {"message": "Job was not in saved list", "job_id": job_id}

    db.delete(saved_job)
    db.commit()

    logger.info(f"Job {job_id} unsaved by user {effective_user.id}")

    return {"message": "Job removed from saved list", "job_id": job_id}


@router.get("", response_model=schemas.subscription.DashboardResponse)
def get_dashboard(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
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
    - Total jobs available (all posted jobs in database)
    - Top 20 matched jobs (id, trs_score, permit_type, country_city, state)
    """
    # Check user role (based on main account)
    if effective_user.role not in ["Contractor", "Supplier"]:
        raise HTTPException(
            status_code=403,
            detail="User must be a Contractor or Supplier to access dashboard",
        )

    # Get user profile
    user_profile = None
    profile_completed_at = None

    if effective_user.role == "Contractor":
        contractor = (
            db.query(models.user.Contractor)
            .filter(models.user.Contractor.user_id == effective_user.id)
            .first()
        )
        if contractor and contractor.is_completed:
            user_profile = contractor
            profile_completed_at = contractor.updated_at or contractor.created_at
    else:  # Supplier
        supplier = (
            db.query(models.user.Supplier)
            .filter(models.user.Supplier.user_id == effective_user.id)
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
        .filter(models.user.Subscriber.user_id == effective_user.id)
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

                # Format renewal date as "8 January 2026"
                if subscriber.subscription_renew_date:
                    renewal_date = subscriber.subscription_renew_date.strftime("%#d %B %Y")

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
            .filter(models.user.UnlockedLead.user_id == effective_user.id)
            .scalar()
            or 0
        )
        if credit_balance == 0 and total_spent == 0:
            plan_name = "Free Plan"
            renewal_date = None

    # Get total jobs unlocked
    total_jobs_unlocked = (
        db.query(models.user.UnlockedLead)
        .filter(models.user.UnlockedLead.user_id == effective_user.id)
        .count()
    )

    # Format profile completion month
    profile_completion_month = None
    if profile_completed_at:
        profile_completion_month = profile_completed_at.strftime("%B %Y")

    # Get top 20 matched jobs using audience_type_slugs matching
    search_conditions = []

    if current_user.role == "Contractor":
        # Get user type array from contractor
        user_types_raw = user_profile.user_type if user_profile.user_type else []
        
        # Split comma-separated values within array elements
        user_types = []
        for item in user_types_raw:
            # Split by comma and strip whitespace
            user_types.extend([ut.strip() for ut in item.split(",") if ut.strip()])
        
        # Match if ANY user_type matches ANY value in audience_type_slugs
        if user_types:
            audience_conditions = []
            for user_type in user_types:
                audience_conditions.append(
                    models.user.Job.audience_type_slugs.ilike(f"%{user_type}%")
                )
            if audience_conditions:
                search_conditions.append(or_(*audience_conditions))

        # Location filters
        contractor_states = user_profile.state if user_profile.state else []
        contractor_country_cities = (
            user_profile.country_city if user_profile.country_city else []
        )

    else:  # Supplier
        # Get user type array from supplier
        user_types_raw = user_profile.user_type if user_profile.user_type else []
        
        # Split comma-separated values within array elements
        user_types = []
        for item in user_types_raw:
            # Split by comma and strip whitespace
            user_types.extend([ut.strip() for ut in item.split(",") if ut.strip()])
        
        # Match if ANY user_type matches ANY value in audience_type_slugs
        if user_types:
            audience_conditions = []
            for user_type in user_types:
                audience_conditions.append(
                    models.user.Job.audience_type_slugs.ilike(f"%{user_type}%")
                )
            if audience_conditions:
                search_conditions.append(or_(*audience_conditions))

        # Location filters
        contractor_states = (
            user_profile.service_states if user_profile.service_states else []
        )
        contractor_country_cities = (
            user_profile.country_city if user_profile.country_city else []
        )

    # Get list of not-interested job IDs for this user (main account)
    not_interested_job_ids = (
        db.query(models.user.NotInterestedJob.job_id)
        .filter(models.user.NotInterestedJob.user_id == effective_user.id)
        .all()
    )
    not_interested_ids = [job_id[0] for job_id in not_interested_job_ids]

    # Get list of unlocked job IDs for this user (main account)
    unlocked_job_ids = (
        db.query(models.user.UnlockedLead.job_id)
        .filter(models.user.UnlockedLead.user_id == effective_user.id)
        .all()
    )
    unlocked_ids = [job_id[0] for job_id in unlocked_job_ids]

    # Get list of saved job IDs for this user (main account)
    saved_job_ids_rows = (
        db.query(models.user.SavedJob.job_id)
        .filter(models.user.SavedJob.user_id == effective_user.id)
        .all()
    )
    saved_ids = [job_id[0] for job_id in saved_job_ids_rows]

    # Combine excluded IDs (not-interested, unlocked, saved)
    excluded_ids = list(set(not_interested_ids + unlocked_ids + saved_ids))

    # Build base query - FILTER FOR POSTED JOBS FIRST
    base_query = db.query(models.user.Job).filter(
        models.user.Job.job_review_status == "posted"
    )

    # Exclude not-interested, unlocked, and saved jobs
    if excluded_ids:
        base_query = base_query.filter(~models.user.Job.id.in_(excluded_ids))

    # Apply user_type matching
    if search_conditions:
        base_query = base_query.filter(or_(*search_conditions))

    # Filter by states (match ANY state in array)
    if contractor_states and len(contractor_states) > 0:
        state_conditions = [
            models.user.Job.state.ilike(f"%{state}%") for state in contractor_states
        ]
        base_query = base_query.filter(or_(*state_conditions))

    # Filter by source_county (match ANY city/county in array)
    if contractor_country_cities and len(contractor_country_cities) > 0:
        city_conditions = [
            models.user.Job.source_county.ilike(f"%{city}%")
            for city in contractor_country_cities
        ]
        base_query = base_query.filter(or_(*city_conditions))

    # Get all matched jobs for deduplication
    all_jobs = base_query.order_by(models.user.Job.review_posted_at.desc()).all()
    
    # Deduplicate jobs by (permit_type_norm, project_description, contractor_name, contractor_email)
    seen_jobs = set()
    deduplicated_jobs = []
    
    for job in all_jobs:
        job_key = (
            (job.permit_type_norm or "").lower().strip(),
            (job.project_description or "").lower().strip()[:200],
            (job.contractor_name or "").lower().strip(),
            (job.contractor_email or "").lower().strip()
        )
        
        if job_key not in seen_jobs:
            seen_jobs.add(job_key)
            deduplicated_jobs.append(job)
    
    logger.info(f"Dashboard: {len(all_jobs)} jobs → {len(deduplicated_jobs)} unique ({len(all_jobs) - len(deduplicated_jobs)} duplicates removed)")
    
    # Get top 20 from deduplicated results
    top_jobs = deduplicated_jobs[:20]

    # Determine which of the top jobs the user has saved
    top_job_ids = [job.id for job in top_jobs]
    saved_jobs_rows = (
        (
            db.query(models.user.SavedJob.job_id)
            .filter(models.user.SavedJob.user_id == effective_user.id)
            .filter(models.user.SavedJob.job_id.in_(top_job_ids))
            .all()
        )
        if top_job_ids
        else []
    )
    saved_job_ids = {r[0] for r in saved_jobs_rows}

    # Convert to summary format and include `saved` boolean
    top_matched_jobs = [
        {
            "id": job.id,
            "permit_type_norm": job.audience_type_names,  # Use audience_type_names for human-readable format
            "source_county": job.source_county,
            "state": job.state,
            "project_description": job.project_description,
            "project_cost_total": job.project_cost_total,
            "property_type": job.property_type,
            "trs_score": job.trs_score,
            "review_posted_at": job.review_posted_at,
            "saved": job.id in saved_job_ids,
        }
        for job in top_jobs
    ]

    # Log the job IDs being sent to user
    job_ids_sent = [job["id"] for job in top_matched_jobs]
    logger.info(
        f"Dashboard GET - User {effective_user.id} ({effective_user.role}) - Sending {len(job_ids_sent)} jobs: {job_ids_sent}"
    )

    # Total jobs available is the count of ALL posted jobs in the database
    total_jobs_available = (
        db.query(models.user.Job)
        .filter(models.user.Job.job_review_status == "posted")
        .count()
    )

    # Calculate jobs unlocked by month (last 6 months, cumulative)
    jobs_unlocked_by_month = []
    current_date = datetime.now()

    for i in range(5, -1, -1):  # 6 months ago to current month
        month_start = (current_date - relativedelta(months=i)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        month_end = (month_start + relativedelta(months=1)) - timedelta(seconds=1)

        # Count jobs unlocked up to this month (cumulative)
        jobs_count = (
            db.query(models.user.UnlockedLead)
            .filter(
                models.user.UnlockedLead.user_id == effective_user.id,
                models.user.UnlockedLead.unlocked_at <= month_end,
            )
            .count()
        )

        month_name = month_start.strftime("%b")  # "Jan", "Feb", etc.
        jobs_unlocked_by_month.append({"month": month_name, "value": jobs_count})

    # Calculate credits used by month (last 7 months, per month)
    credits_used_by_month = []

    for i in range(6, -1, -1):  # 7 months ago to current month
        month_start = (current_date - relativedelta(months=i)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        month_end = (month_start + relativedelta(months=1)) - timedelta(seconds=1)

        # Sum credits spent in this specific month
        credits_spent = (
            db.query(func.sum(models.user.UnlockedLead.credits_spent))
            .filter(
                models.user.UnlockedLead.user_id == effective_user.id,
                models.user.UnlockedLead.unlocked_at >= month_start,
                models.user.UnlockedLead.unlocked_at <= month_end,
            )
            .scalar()
        ) or 0

        month_name = month_start.strftime("%b")  # "Jan", "Feb", etc.
        credits_used_by_month.append({"month": month_name, "value": credits_spent})

    return {
        "credit_balance": credit_balance,
        "credits_added_this_week": credits_added_this_week,
        "plan_name": plan_name,
        "renewal_date": renewal_date,
        "profile_completion_month": profile_completion_month,
        "total_jobs_unlocked": total_jobs_unlocked,
        "total_jobs_available": total_jobs_available,
        "top_matched_jobs": top_matched_jobs,
        "jobs_unlocked_by_month": jobs_unlocked_by_month,
        "credits_used_by_month": credits_used_by_month,
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

    # Get saved job IDs
    saved_job_ids_rows = (
        db.query(models.user.SavedJob.job_id)
        .filter(models.user.SavedJob.user_id == current_user.id)
        .all()
    )
    saved_ids = [job_id[0] for job_id in saved_job_ids_rows]

    # Combine all IDs to exclude (from URL params, not-interested, unlocked, saved)
    all_excluded_ids = list(set(exclude_job_ids + not_interested_ids + unlocked_ids + saved_ids))

    # Build search conditions
    search_conditions = []

    if current_user.role == "Contractor":
        # Get user type array from contractor
        user_types_raw = user_profile.user_type if user_profile.user_type else []
        
        # Split comma-separated values within array elements
        user_types = []
        for item in user_types_raw:
            # Split by comma and strip whitespace
            user_types.extend([ut.strip() for ut in item.split(",") if ut.strip()])
        
        # Match if ANY user_type matches ANY value in audience_type_slugs
        if user_types:
            audience_conditions = []
            for user_type in user_types:
                audience_conditions.append(
                    models.user.Job.audience_type_slugs.ilike(f"%{user_type}%")
                )
            if audience_conditions:
                search_conditions.append(or_(*audience_conditions))

        contractor_states = user_profile.state if user_profile.state else []
        contractor_country_cities = (
            user_profile.country_city if user_profile.country_city else []
        )

    else:  # Supplier
        # Get user type array from supplier
        user_types_raw = user_profile.user_type if user_profile.user_type else []
        
        # Split comma-separated values within array elements
        user_types = []
        for item in user_types_raw:
            # Split by comma and strip whitespace
            user_types.extend([ut.strip() for ut in item.split(",") if ut.strip()])
        
        # Match if ANY user_type matches ANY value in audience_type_slugs
        if user_types:
            audience_conditions = []
            for user_type in user_types:
                audience_conditions.append(
                    models.user.Job.audience_type_slugs.ilike(f"%{user_type}%")
                )
            if audience_conditions:
                search_conditions.append(or_(*audience_conditions))

        contractor_states = (
            user_profile.service_states if user_profile.service_states else []
        )
        contractor_country_cities = (
            user_profile.country_city if user_profile.country_city else []
        )

    # Build query - FILTER FOR POSTED JOBS FIRST
    base_query = db.query(models.user.Job).filter(
        models.user.Job.job_review_status == "posted"
    )

    # Exclude already shown, not-interested, unlocked, and saved jobs
    if all_excluded_ids:
        base_query = base_query.filter(~models.user.Job.id.in_(all_excluded_ids))

    # Apply user_type matching
    if search_conditions:
        base_query = base_query.filter(or_(*search_conditions))

    # Filter by location
    if contractor_states and len(contractor_states) > 0:
        state_conditions = [
            models.user.Job.state.ilike(f"%{state}%") for state in contractor_states
        ]
        base_query = base_query.filter(or_(*state_conditions))

    if contractor_country_cities and len(contractor_country_cities) > 0:
        city_conditions = [
            models.user.Job.source_county.ilike(f"%{city}%")
            for city in contractor_country_cities
        ]
        base_query = base_query.filter(or_(*city_conditions))

    # Get all matched jobs for deduplication
    all_jobs = base_query.order_by(models.user.Job.review_posted_at.desc()).all()
    
    # Deduplicate jobs by (permit_type_norm, project_description, contractor_name, contractor_email)
    seen_jobs = set()
    deduplicated_jobs = []
    
    for job in all_jobs:
        job_key = (
            (job.permit_type_norm or "").lower().strip(),
            (job.project_description or "").lower().strip()[:200],
            (job.contractor_name or "").lower().strip(),
            (job.contractor_email or "").lower().strip()
        )
        
        if job_key not in seen_jobs:
            seen_jobs.add(job_key)
            deduplicated_jobs.append(job)
    
    logger.info(f"Dashboard/matched-jobs: {len(all_jobs)} jobs → {len(deduplicated_jobs)} unique ({len(all_jobs) - len(deduplicated_jobs)} duplicates removed)")
    
    # Get limited results from deduplicated list
    jobs = deduplicated_jobs[:limit]
    total_count = len(deduplicated_jobs)

    # Determine which of the returned jobs the user has saved
    job_ids = [job.id for job in jobs]
    saved_rows = (
        (
            db.query(models.user.SavedJob.job_id)
            .filter(models.user.SavedJob.user_id == current_user.id)
            .filter(models.user.SavedJob.job_id.in_(job_ids))
            .all()
        )
        if job_ids
        else []
    )
    saved_ids = {r[0] for r in saved_rows}

    # Convert to simplified response format (include `saved` flag)
    job_responses = [
        schemas.subscription.MatchedJobSummary(
            id=job.id,
            permit_type_norm=job.audience_type_names,  # Use audience_type_names for human-readable format
            source_county=job.source_county,
            state=job.state,
            project_description=job.project_description,
            project_cost_total=job.project_cost_total,
            property_type=job.property_type,
            trs_score=job.trs_score,
            review_posted_at=job.review_posted_at,
            saved=(job.id in saved_ids),
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
    If the job was saved, removes it from saved jobs first.
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

    # Remove from saved jobs if it exists
    saved_job = (
        db.query(models.user.SavedJob)
        .filter(
            models.user.SavedJob.user_id == current_user.id,
            models.user.SavedJob.job_id == job_id,
        )
        .first()
    )
    
    if saved_job:
        db.delete(saved_job)

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
    # Get the job - only posted jobs can be unlocked
    job = db.query(models.user.Job).filter(
        models.user.Job.id == job_id,
        models.user.Job.job_review_status == 'posted'
    ).first()

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
                "permit_number": job.permit_number or "N/A",
                "permit_type_norm": job.audience_type_names or "N/A",  # Use audience_type_names for human-readable format
                "project_cost_total": job.project_cost_total or "N/A",
                "job_address": job.job_address or "N/A",
                "contractor_email": job.contractor_email or "N/A",
                "contractor_phone": job.contractor_phone or "N/A",
                "source_county": job.source_county or "N/A",
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

    # Use TRS score as credit cost (TRS is in range 10-20)
    credits_needed = job.trs_score if job.trs_score else 10

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
            "permit_number": job.permit_number or "N/A",
            "permit_type_norm": job.audience_type_names or "N/A",  # Use audience_type_names for human-readable format
            "project_cost_total": job.project_cost_total or "N/A",
            "job_address": job.job_address or "N/A",
            "contractor_email": job.contractor_email or "N/A",
            "contractor_phone": job.contractor_phone or "N/A",
            "source_county": job.source_county or "N/A",
            "state": job.state or "N/A",
            "project_description": job.project_description or "N/A",
        },
    }
