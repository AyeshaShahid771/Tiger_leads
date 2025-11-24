import csv
import io
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from src.app import models, schemas
from src.app.api.deps import get_current_user
from src.app.core.database import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post("/upload-leads", response_model=schemas.subscription.BulkUploadResponse)
async def upload_leads(
    file: UploadFile = File(...),
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Bulk upload leads/jobs from CSV or Excel file.

    Expected columns:
    - permit_record_number
    - date (YYYY-MM-DD format)
    - permit_type
    - project_description
    - job_address
    - job_cost
    - permit_status
    - email
    - phone_number
    - country
    - city
    - state
    - work_type
    - credit_cost (optional, defaults to 1)
    - category (optional)

    Admin/authorized users only.
    """
    # Check if user is authorized (you can add admin check here)
    # For now, allowing any authenticated user

    # Validate file type
    allowed_extensions = [".csv", ".xlsx", ".xls"]
    file_ext = file.filename.lower().split(".")[-1]
    if f".{file_ext}" not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Only CSV and Excel files are supported.",
        )

    try:
        # Read file content
        contents = await file.read()

        # Parse file based on extension
        if file_ext == "csv":
            df = pd.read_csv(io.BytesIO(contents))
        else:  # xlsx or xls
            df = pd.read_excel(io.BytesIO(contents))

        total_rows = len(df)
        successful = 0
        failed = 0
        errors = []

        # Column mapping (handle different column name variations)
        column_mapping = {
            "permit_record_number": [
                "permit_record_number",
                "permit_number",
                "record_number",
            ],
            "date": ["date", "job_date", "permit_date"],
            "permit_type": ["permit_type", "type"],
            "project_description": [
                "project_description",
                "description",
                "project_desc",
            ],
            "job_address": ["job_address", "address", "location"],
            "job_cost": ["job_cost", "project_value", "cost"],
            "permit_status": ["permit_status", "status"],
            "email": ["email", "contact_email"],
            "phone_number": ["phone_number", "phone", "contact_phone"],
            "country": ["country"],
            "city": ["city"],
            "state": ["state"],
            "work_type": ["work_type", "type_of_work"],
            "credit_cost": ["credit_cost", "credits", "cost_in_credits"],
            "category": ["category", "lead_category"],
        }

        # Normalize column names
        df.columns = df.columns.str.lower().str.strip()

        # Process each row
        for index, row in df.iterrows():
            try:
                # Extract values with fallback to None
                def get_value(field_name):
                    possible_names = column_mapping.get(field_name, [field_name])
                    for name in possible_names:
                        if name in df.columns and pd.notna(row.get(name)):
                            return row.get(name)
                    return None

                # Parse date
                date_value = get_value("date")
                parsed_date = None
                if date_value:
                    try:
                        parsed_date = pd.to_datetime(date_value).date()
                    except:
                        parsed_date = None

                # Get credit cost with default
                credit_cost = get_value("credit_cost")
                if credit_cost is None or pd.isna(credit_cost):
                    credit_cost = 1
                else:
                    try:
                        credit_cost = int(credit_cost)
                    except:
                        credit_cost = 1

                # Create job object
                job = models.user.Job(
                    permit_record_number=(
                        str(get_value("permit_record_number"))
                        if get_value("permit_record_number")
                        else None
                    ),
                    date=parsed_date,
                    permit_type=(
                        str(get_value("permit_type"))
                        if get_value("permit_type")
                        else None
                    ),
                    project_description=(
                        str(get_value("project_description"))
                        if get_value("project_description")
                        else None
                    ),
                    job_address=(
                        str(get_value("job_address"))
                        if get_value("job_address")
                        else None
                    ),
                    job_cost=(
                        str(get_value("job_cost")) if get_value("job_cost") else None
                    ),
                    permit_status=(
                        str(get_value("permit_status"))
                        if get_value("permit_status")
                        else None
                    ),
                    email=str(get_value("email")) if get_value("email") else None,
                    phone_number=(
                        str(get_value("phone_number"))
                        if get_value("phone_number")
                        else None
                    ),
                    country=str(get_value("country")) if get_value("country") else None,
                    city=str(get_value("city")) if get_value("city") else None,
                    state=str(get_value("state")) if get_value("state") else None,
                    work_type=(
                        str(get_value("work_type")) if get_value("work_type") else None
                    ),
                    credit_cost=credit_cost,
                    category=(
                        str(get_value("category")) if get_value("category") else None
                    ),
                )

                db.add(job)
                successful += 1

            except Exception as e:
                failed += 1
                errors.append(f"Row {index + 2}: {str(e)}")
                logger.error(f"Error processing row {index + 2}: {str(e)}")

        # Commit all successful inserts
        db.commit()

        logger.info(
            f"Bulk upload completed: {successful} successful, {failed} failed out of {total_rows} total"
        )

        return {
            "total_rows": total_rows,
            "successful": successful,
            "failed": failed,
            "errors": errors[:50],  # Return first 50 errors
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error during bulk upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")


@router.post("/filter")
def filter_jobs(
    filters: schemas.subscription.FilterRequest,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    """
    Filter jobs based on cities, countries, work types, and states.
    Also filters based on user's profile (contractor/supplier).
    """
    # Check user role and profile completion
    if current_user.role == "Contractor":
        contractor = (
            db.query(models.user.Contractor)
            .filter(models.user.Contractor.user_id == current_user.id)
            .first()
        )
        if not contractor or not contractor.is_completed:
            raise HTTPException(
                status_code=403, detail="Please complete your contractor profile first"
            )
        user_profile = contractor
    elif current_user.role == "Supplier":
        supplier = (
            db.query(models.user.Supplier)
            .filter(models.user.Supplier.user_id == current_user.id)
            .first()
        )
        if not supplier or not supplier.is_completed:
            raise HTTPException(
                status_code=403, detail="Please complete your supplier profile first"
            )
        user_profile = supplier
    else:
        raise HTTPException(
            status_code=403, detail="User must be a Contractor or Supplier"
        )

    # Build query
    query = db.query(models.user.Job)

    # Apply filters from request
    filter_conditions = []

    if filters.cities:
        filter_conditions.append(models.user.Job.city.in_(filters.cities))

    if filters.countries:
        filter_conditions.append(models.user.Job.country.in_(filters.countries))

    if filters.work_types:
        filter_conditions.append(models.user.Job.work_type.in_(filters.work_types))

    if filters.states:
        filter_conditions.append(models.user.Job.state.in_(filters.states))

    # Apply profile-based filters
    if current_user.role == "Contractor":
        # Filter by contractor's state and work type
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

    elif current_user.role == "Supplier":
        # Filter by supplier's service states
        if user_profile.service_states:
            service_states = json.loads(user_profile.service_states)
            filter_conditions.append(models.user.Job.state.in_(service_states))
        # Filter by supplier's product categories
        if user_profile.product_categories:
            product_categories = json.loads(user_profile.product_categories)
            filter_conditions.append(models.user.Job.category.in_(product_categories))

    if filter_conditions:
        query = query.filter(and_(*filter_conditions))

    # Get total count
    total_jobs = query.count()

    # Pagination
    offset = (page - 1) * page_size
    jobs = (
        query.order_by(models.user.Job.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    # Convert to response format (hide sensitive data)
    jobs_response = [
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
        for job in jobs
    ]

    return {
        "jobs": jobs_response,
        "total": total_jobs,
        "page": page,
        "page_size": page_size,
        "total_pages": (total_jobs + page_size - 1) // page_size,
    }


@router.post("/unlock/{job_id}", response_model=schemas.subscription.JobDetailResponse)
def unlock_job(
    job_id: int,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unlock a job/lead by spending credits."""
    # Check if job exists
    job = db.query(models.user.Job).filter(models.user.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check if already unlocked
    already_unlocked = (
        db.query(models.user.UnlockedLead)
        .filter(
            and_(
                models.user.UnlockedLead.user_id == current_user.id,
                models.user.UnlockedLead.job_id == job_id,
            )
        )
        .first()
    )

    if already_unlocked:
        # Return full job details if already unlocked
        return job

    # Get credit cost for this job
    credit_cost = job.credit_cost if job.credit_cost else 1

    # Get subscriber info
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.user_id == current_user.id)
        .first()
    )

    if not subscriber or subscriber.current_credits < credit_cost:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient credits. This job requires {credit_cost} credits. Please purchase a subscription.",
        )

    # Deduct credits
    subscriber.current_credits -= credit_cost
    subscriber.total_spending += credit_cost

    # Create unlocked lead record
    unlocked_lead = models.user.UnlockedLead(
        user_id=current_user.id, job_id=job_id, credits_spent=credit_cost
    )

    db.add(unlocked_lead)
    db.commit()
    db.refresh(subscriber)

    logger.info(
        f"User {current_user.email} unlocked job {job_id} for {credit_cost} credits"
    )

    return job


@router.get("/my-unlocked-leads")
def get_my_unlocked_leads(
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    """Get all unlocked leads for the current user."""
    # Get total count
    total = (
        db.query(models.user.UnlockedLead)
        .filter(models.user.UnlockedLead.user_id == current_user.id)
        .count()
    )

    # Get paginated unlocked leads with job details
    offset = (page - 1) * page_size
    unlocked_leads = (
        db.query(models.user.UnlockedLead, models.user.Job)
        .join(models.user.Job, models.user.UnlockedLead.job_id == models.user.Job.id)
        .filter(models.user.UnlockedLead.user_id == current_user.id)
        .order_by(models.user.UnlockedLead.unlocked_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    leads_response = [
        {
            "unlocked_lead_id": lead.id,
            "job_id": job.id,
            "permit_record_number": job.permit_record_number,
            "date": job.date,
            "permit_type": job.permit_type,
            "project_description": job.project_description,
            "job_address": job.job_address,
            "job_cost": job.job_cost,
            "permit_status": job.permit_status,
            "email": job.email,
            "phone_number": job.phone_number,
            "country": job.country,
            "city": job.city,
            "state": job.state,
            "work_type": job.work_type,
            "credits_spent": lead.credits_spent,
            "unlocked_at": lead.unlocked_at,
        }
        for lead, job in unlocked_leads
    ]

    return {
        "unlocked_leads": leads_response,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/export-unlocked-leads")
def export_unlocked_leads(
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export all unlocked leads to CSV."""
    # Get all unlocked leads with job details
    unlocked_leads = (
        db.query(models.user.UnlockedLead, models.user.Job)
        .join(models.user.Job, models.user.UnlockedLead.job_id == models.user.Job.id)
        .filter(models.user.UnlockedLead.user_id == current_user.id)
        .order_by(models.user.UnlockedLead.unlocked_at.desc())
        .all()
    )

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(
        [
            "Permit/Record #",
            "Date",
            "Permit Type",
            "Project Description",
            "Job Address",
            "Job Cost/Project Value",
            "Permit Status",
            "Email",
            "Phone Number",
            "Country",
            "City",
            "State",
            "Work Type",
            "Unlocked At",
            "Credits Spent",
        ]
    )

    # Write data
    for lead, job in unlocked_leads:
        writer.writerow(
            [
                job.permit_record_number,
                job.date,
                job.permit_type,
                job.project_description,
                job.job_address,
                job.job_cost,
                job.permit_status,
                job.email,
                job.phone_number,
                job.country,
                job.city,
                job.state,
                job.work_type,
                lead.unlocked_at,
                lead.credits_spent,
            ]
        )

    output.seek(0)

    # Return as streaming response
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=unlocked_leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        },
    )
