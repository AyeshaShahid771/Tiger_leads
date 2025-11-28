import csv
import io
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

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

# US Counties and Cities mapping (hardcoded for reliability)
US_COUNTIES = {
    "gwinnett": "GA",
    "hillsborough": "FL",
    "fulton": "GA",
    "dekalb": "GA",
    "cobb": "GA",
    "orange": "FL",
    "miami-dade": "FL",
    "broward": "FL",
    "palm beach": "FL",
    "pinellas": "FL",
    "duval": "FL",
    "lee": "FL",
    "polk": "FL",
    "brevard": "FL",
    "volusia": "FL",
    "pasco": "FL",
    "seminole": "FL",
    "manatee": "FL",
    "sarasota": "FL",
    "osceola": "FL",
}

US_CITIES = {
    "atlanta": "GA",
    "tampa": "FL",
    "miami": "FL",
    "orlando": "FL",
    "jacksonville": "FL",
    "st. petersburg": "FL",
    "fort lauderdale": "FL",
    "west palm beach": "FL",
    "clearwater": "FL",
    "lakeland": "FL",
    "melbourne": "FL",
    "daytona beach": "FL",
    "fort myers": "FL",
    "naples": "FL",
    "sarasota": "FL",
}


# TRS (Total Relevance Score) Calculation Helper Functions
def project_value_score(project_value):
    """
    Calculate score based on project value.
    Returns: 30, 50, or 95
    """
    # If no value is provided
    if project_value is None:
        return 50

    try:
        # Convert to float, handling string inputs with $ and commas
        if isinstance(project_value, str):
            # Remove dollar signs, commas, and whitespace
            clean_value = project_value.replace("$", "").replace(",", "").strip()
            project_value = float(clean_value)
        else:
            project_value = float(project_value)
    except (ValueError, TypeError):
        return 50

    # Smallest values (< 5000)
    if project_value < 5000:
        return 30

    # Mid-Range (5000 to < 15000)
    if project_value < 15000:
        return 50

    # Project Value Range (15000 to < 50000)
    if project_value < 50000:
        return 50

    # Largest values (>= 50000)
    return 95


def stage_score(status):
    """
    Calculate score based on permit status/stage.
    Returns: 10, 30, 50, 60, or 90
    """
    status = (status or "").lower()

    if status in ["pre-application", "concept"]:
        return 30
    if status in ["applied", "in review"]:
        return 60
    if status in ["issued", "ready to start", "under construction"]:
        return 90
    if status in ["finaled", "closed", "expired"]:
        return 10

    return 50  # default


def contact_score(phone_number, email):
    """
    Calculate score based on contact information availability.
    Returns: 10, 50, or 80
    """
    phone_present = phone_number is not None and str(phone_number).strip() != ""
    email_present = email is not None and str(email).strip() != ""

    if phone_present:
        return 80
    if email_present:
        return 50

    return 10


def calculate_trs_score(project_value, permit_status, phone_number, email):
    """
    Calculate Total Relevance Score (TRS) based on project value, status, and contact info.
    TRS = (project_value_score + stage_score + contact_score) / 3
    Returns: Integer score between 0-100
    """
    pv_score = project_value_score(project_value)
    st_score = stage_score(permit_status)
    ct_score = contact_score(phone_number, email)

    # Average of the three scores
    trs = (pv_score + st_score + ct_score) / 3

    return int(round(trs))


def classify_us_location(
    location_name: str, state_hint: str = None
) -> Tuple[str, str, str, bool]:
    """
    Classify a US location name as city or county and determine its state.
    Uses hardcoded US counties/cities mapping for reliability.

    Args:
        location_name: Name like "Gwinnett", "Hillsborough", "Atlanta"
        state_hint: Optional state code to narrow search (e.g., "FL", "GA")

    Returns:
        Tuple of (location_name, detected_state, is_county)
        - location_name: The location name
        - detected_state: State code (e.g., "FL", "GA") or state_hint if not found
        - is_county: True if it's a county, False if it's a city

    Example:
        classify_us_location("Gwinnett", "GA") → ("Gwinnett", "GA", True)  # County
        classify_us_location("Atlanta", "GA") → ("Atlanta", "GA", False)  # City
        classify_us_location("Hillsborough") → ("Hillsborough", "FL", True)  # County
    """
    if not location_name or location_name.strip() == "":
        return None, state_hint, False

    location_name_original = location_name.strip()
    location_name_lower = location_name_original.lower()

    # Check if it's a known city first
    if location_name_lower in US_CITIES:
        detected_state = US_CITIES[location_name_lower]
        logger.info(
            f"Location '{location_name_original}' classified as CITY in state: {detected_state}"
        )
        return location_name_original, detected_state, False  # It's a city

    # Check if it's a known county
    if location_name_lower in US_COUNTIES:
        detected_state = US_COUNTIES[location_name_lower]
        logger.info(
            f"Location '{location_name_original}' classified as COUNTY in state: {detected_state}"
        )
        return location_name_original, detected_state, True  # It's a county

    # If we have a state hint, trust it and assume it's a county (default assumption)
    if state_hint:
        logger.info(
            f"Location '{location_name_original}' not in predefined list, but has state hint: {state_hint}, assuming COUNTY"
        )
        return location_name_original, state_hint, True  # Assume county by default

    # Fallback: location not in our list, assume county
    logger.warning(
        f"Location '{location_name_original}' not found in US database, storing as COUNTY"
    )
    return location_name_original, state_hint, True  # Assume county by default


@router.post("/upload-leads", response_model=schemas.subscription.BulkUploadResponse)
async def upload_leads(
    file: UploadFile = File(...),
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Bulk upload leads/jobs from CSV or Excel file with automatic TRS scoring and US location classification.

    Expected columns:
    - permit_record_number (or "Permit/Record #")
    - date (YYYY-MM-DD format)
    - permit_type (or "Permit Type")
    - project_description (or "Project Description")
    - job_address (or "Job Address")
    - job_cost (or "Job Cost/Project Value")
    - permit_status (or "Permit Status")
    - email (or "Contractor Email")
    - phone_number (or "Contractor Phone #")
    - county/city (auto-classifies US counties/cities and sets country="USA")
    - state (optional, auto-detected if missing)
    - country (optional, auto-set to "USA" for US locations)
    - work_type (optional)
    - credit_cost (optional, defaults to 1)
    - category (optional)

    Features:
    - Automatic TRS (Total Relevance Score) calculation for each lead
    - US location classification using uszipcode database
    - Auto-detects if location is city or county
    - Auto-sets country to "USA" for US locations
    - Auto-detects state if not provided

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
                "permit/record #",
            ],
            "date": ["date", "job_date", "permit_date"],
            "permit_type": ["permit_type", "type", "permit type"],
            "project_description": [
                "project_description",
                "description",
                "project_desc",
                "project description",
            ],
            "job_address": ["job_address", "address", "location", "job address"],
            "job_cost": ["job_cost", "project_value", "cost", "job cost/project value"],
            "permit_status": ["permit_status", "status", "permit status"],
            "email": ["email", "contact_email", "contractor email"],
            "phone_number": [
                "phone_number",
                "phone",
                "contact_phone",
                "contractor phone #",
            ],
            "country": ["country"],
            "city": ["city", "county/city"],
            "state": ["state"],
            "work_type": ["work_type", "type_of_work"],
            "credit_cost": ["credit_cost", "credits", "cost_in_credits"],
            "category": ["category", "lead_category"],
        }

        # Normalize column names
        df.columns = df.columns.str.lower().str.strip()

        # Process each row
        for index, row in df.iterrows():
            # Extract values with fallback to None
            def get_value(field_name):
                possible_names = column_mapping.get(field_name, [field_name])
                for name in possible_names:
                    if name in df.columns and pd.notna(row.get(name)):
                        return row.get(name)
                return None

            # Parse date (with error handling)
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

            # Extract values for TRS calculation (always succeeds with defaults)
            job_cost_value = get_value("job_cost")
            permit_status_value = (
                str(get_value("permit_status")) if get_value("permit_status") else None
            )
            email_value = str(get_value("email")) if get_value("email") else None
            phone_number_value = (
                str(get_value("phone_number")) if get_value("phone_number") else None
            )

            # Calculate TRS score (ALWAYS calculated, uses defaults for missing values)
            trs = calculate_trs_score(
                job_cost_value, permit_status_value, phone_number_value, email_value
            )

            # US Location Classification (City/County detection)
            raw_city_value = get_value("city")
            raw_country_value = get_value("country")
            raw_state_value = get_value("state")

            # State is always provided, use it as hint for classification
            state_hint = str(raw_state_value) if raw_state_value else None

            # Determine which field contains the location name (city/county)
            # Could be in 'city' column OR 'country' column (Excel varies)
            location_name = None

            if raw_city_value:
                # Location is in city/county column
                location_name = str(raw_city_value)
            elif raw_country_value:
                # Location is in country column (misplaced data)
                location_name = str(raw_country_value)

            # If we have a location name, classify it as US location
            if location_name:
                location_classified, state_classified, is_county = classify_us_location(
                    location_name, state_hint
                )

                # Separate city and county into correct columns
                if is_county:
                    # It's a county -> store in country column
                    final_city = None
                    final_country = location_classified
                else:
                    # It's a city -> store in city column
                    final_city = location_classified
                    final_country = None

                # Keep the original state (always provided)
                final_state = state_hint if state_hint else state_classified
            else:
                # No location data at all
                final_city = None
                final_country = None
                final_state = state_hint

            try:
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
                    permit_status=permit_status_value,
                    email=email_value,
                    phone_number=phone_number_value,
                    country=final_country,
                    city=final_city,
                    state=final_state,
                    work_type=(
                        str(get_value("work_type")) if get_value("work_type") else None
                    ),
                    credit_cost=credit_cost,
                    category=(
                        str(get_value("category")) if get_value("category") else None
                    ),
                    trs_score=trs,  # TRS ALWAYS assigned
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
        # Contractor's primary trade category (single string)
        if getattr(user_profile, "trade_categories", None):
            filter_conditions.append(
                models.user.Job.work_type == user_profile.trade_categories
            )
        # Contractor's trade specialities (multiple categories)
        if getattr(user_profile, "trade_specialities", None):
            ts = user_profile.trade_specialities
            # Handle both string (JSON) and native list/array types
            if isinstance(ts, str):
                try:
                    specialities = json.loads(ts)
                except Exception:
                    specialities = [ts]
            else:
                # assume array/list-like
                specialities = list(ts)

            filter_conditions.append(models.user.Job.category.in_(specialities))

    elif current_user.role == "Supplier":
        # Filter by supplier's service states
        if user_profile.service_states:
            service_states = json.loads(user_profile.service_states)
            filter_conditions.append(models.user.Job.state.in_(service_states))
        # Supplier primary product category (matches job.work_type)
        if getattr(user_profile, "product_categories", None):
            filter_conditions.append(
                models.user.Job.work_type == user_profile.product_categories
            )
        # Supplier product types (multiple subcategories) -> match against job.category
        if getattr(user_profile, "product_types", None):
            pt = user_profile.product_types
            if isinstance(pt, str):
                try:
                    product_types = json.loads(pt)
                except Exception:
                    product_types = [pt]
            else:
                product_types = list(pt)

            filter_conditions.append(models.user.Job.category.in_(product_types))

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
