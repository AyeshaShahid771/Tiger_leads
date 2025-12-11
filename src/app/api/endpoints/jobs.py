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
from src.app.data import product_keywords, trade_keywords, us_locations

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


# TRS (Total Relevance Score) Calculation Helper Functions
def project_value_score(project_value):
    """
    Calculate score based on project value with more granular buckets.
    Returns: Score between 20-100 with more variation
    """
    # If no value is provided
    if project_value is None or project_value == "":
        return 50

    try:
        # Convert to float, handling string inputs with $ and commas
        if isinstance(project_value, str):
            # Remove dollar signs, commas, spaces, and any other non-numeric characters except decimal point
            clean_value = (
                project_value.replace("$", "").replace(",", "").replace(" ", "").strip()
            )
            # Remove any other currency symbols or text
            clean_value = "".join(c for c in clean_value if c.isdigit() or c == ".")
            if not clean_value:  # If nothing left after cleaning
                return 50
            project_value = float(clean_value)
        else:
            project_value = float(project_value)
    except (ValueError, TypeError):
        return 50

    # More granular scoring with 10 buckets for better variation
    if project_value < 1000:
        return 20
    elif project_value < 2500:
        return 28
    elif project_value < 5000:
        return 35
    elif project_value < 10000:
        return 45
    elif project_value < 20000:
        return 55
    elif project_value < 35000:
        return 65
    elif project_value < 50000:
        return 72
    elif project_value < 75000:
        return 80
    elif project_value < 100000:
        return 88
    else:  # >= 100000
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


def description_quality_score(project_description):
    """
    Calculate score based on project description quality and detail.
    Returns: Score between 20-100 based on description length and quality
    """
    if not project_description or not str(project_description).strip():
        return 20  # No description

    description = str(project_description).strip()
    length = len(description)

    # Score based on description length (more detail = higher score)
    if length < 20:
        return 30  # Very brief
    elif length < 50:
        return 45  # Short
    elif length < 100:
        return 60  # Moderate
    elif length < 200:
        return 75  # Detailed
    elif length < 350:
        return 85  # Very detailed
    else:  # >= 350 characters
        return 95  # Comprehensive description


def address_completeness_score(job_address):
    """
    Calculate score based on job address completeness and detail.
    Returns: Score between 25-100 based on address components
    """
    if not job_address or not str(job_address).strip():
        return 25  # No address

    address = str(job_address).strip()
    score = 40  # Base score for having an address

    # Check for common address components (each adds points)
    # Street number
    if any(char.isdigit() for char in address[:10]):
        score += 12

    # Street name indicators
    street_indicators = [
        "st",
        "street",
        "ave",
        "avenue",
        "rd",
        "road",
        "blvd",
        "boulevard",
        "ln",
        "lane",
        "dr",
        "drive",
        "way",
        "ct",
        "court",
        "pl",
        "place",
    ]
    if any(indicator in address.lower() for indicator in street_indicators):
        score += 15

    # ZIP code (5 digits)
    if any(part.isdigit() and len(part) == 5 for part in address.split()):
        score += 18

    # Comma separators (indicates structured address)
    comma_count = address.count(",")
    if comma_count >= 1:
        score += 10
    if comma_count >= 2:
        score += 5

    return min(score, 100)  # Cap at 100


def calculate_trs_score(
    project_value,
    permit_status,
    phone_number,
    email,
    project_description=None,
    job_address=None,
):
    """
    Calculate Total Relevance Score (TRS) based on multiple factors.

    Scoring factors:
    - Project Value (weight: 25%)
    - Permit Stage (weight: 25%)
    - Contact Info (weight: 20%)
    - Description Quality (weight: 20%)
    - Address Completeness (weight: 10%)

    Returns: Integer score between 0-100
    """
    pv_score = project_value_score(project_value)
    st_score = stage_score(permit_status)
    ct_score = contact_score(phone_number, email)
    desc_score = description_quality_score(project_description)
    addr_score = address_completeness_score(job_address)

    # Weighted average with more emphasis on value and stage
    trs = (
        (pv_score * 0.25)  # 25% weight
        + (st_score * 0.25)  # 25% weight
        + (ct_score * 0.20)  # 20% weight
        + (desc_score * 0.20)  # 20% weight
        + (addr_score * 0.10)  # 10% weight
    )

    return int(round(trs))


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
            "country_city": [
                "country_city",
                "city_country",
                "country",
                "city",
                "county",
                "country/city",
            ],
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

            # Get description and address for TRS calculation
            project_description_value = get_value("project_description")
            job_address_value = get_value("job_address")

            # Calculate TRS score (ALWAYS calculated, uses defaults for missing values)
            trs = calculate_trs_score(
                job_cost_value,
                permit_status_value,
                phone_number_value,
                email_value,
                project_description_value,
                job_address_value,
            )

            # Location normalization using us_locations library
            raw_country_city_value = get_value("country_city")
            raw_state_value = get_value("state")

            # Format country_city using lookup dictionary
            # If not found in dictionary, store original value from Excel
            final_country_city = None
            if raw_country_city_value:
                formatted_location = us_locations.get_formatted_country_city(
                    str(raw_country_city_value)
                )
                final_country_city = (
                    formatted_location
                    if formatted_location
                    else str(raw_country_city_value)
                )

            # Format state using lookup dictionary (converts abbreviations to full names)
            # If not found in dictionary, store original value from Excel
            final_state = None
            if raw_state_value:
                formatted_state = us_locations.get_state_full_name(str(raw_state_value))
                final_state = (
                    formatted_state if formatted_state else str(raw_state_value)
                )

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
                    country_city=final_country_city,
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
        filter_conditions.append(models.user.Job.country_city.in_(filters.cities))

    if filters.countries:
        filter_conditions.append(models.user.Job.country_city.in_(filters.countries))

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
            "country_city": job.country_city,
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


@router.get("/feed")
def get_job_feed(
    states: Optional[str] = Query(None, description="Comma-separated list of states"),
    countries: Optional[str] = Query(
        None, description="Comma-separated list of countries/cities"
    ),
    categories: Optional[str] = Query(
        None,
        description="Comma-separated list of trade categories (contractor) or product categories (supplier)",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get job feed with custom filters based on user role.

    For Contractors:
    - Matches jobs based on trade categories (using trade keywords)
    - Filters by states and countries/cities

    For Suppliers:
    - Matches jobs based on product categories (using product keywords)
    - Filters by states and countries/cities

    Returns paginated job results with TRS scores.

    Note: At least one filter parameter (states, countries, or categories) is required.
    """
    # Check user role
    if current_user.role not in ["Contractor", "Supplier"]:
        raise HTTPException(
            status_code=403, detail="User must be a Contractor or Supplier"
        )

    # Validate that at least one filter parameter is provided
    if not states and not countries and not categories:
        raise HTTPException(
            status_code=400,
            detail="Please select at least one filter (states, countries, or categories) to get desired jobs",
        )

    # Parse query parameters
    state_list = []
    if states:
        state_list = [s.strip() for s in states.split(",") if s.strip()]

    country_city_list = []
    if countries:
        country_city_list = [c.strip() for c in countries.split(",") if c.strip()]

    category_list = []
    if categories:
        category_list = [cat.strip() for cat in categories.split(",") if cat.strip()]

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

    # Build search conditions based on role
    search_conditions = []

    if current_user.role == "Contractor":
        # Use trade categories and trade keywords
        if category_list:
            for category in category_list:
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

    elif current_user.role == "Supplier":
        # Use product categories and product keywords
        if category_list:
            for category in category_list:
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

    # Build base query
    base_query = db.query(models.user.Job)

    # Exclude not-interested and unlocked jobs
    if excluded_ids:
        base_query = base_query.filter(~models.user.Job.id.in_(excluded_ids))

    # Apply category/keyword search conditions
    if search_conditions:
        base_query = base_query.filter(or_(*search_conditions))

    # Filter by states (match ANY state in the provided list)
    if state_list:
        state_conditions = [
            models.user.Job.state.ilike(f"%{state}%") for state in state_list
        ]
        base_query = base_query.filter(or_(*state_conditions))

    # Filter by country_city (match ANY city/county in the provided list)
    if country_city_list:
        city_conditions = [
            models.user.Job.country_city.ilike(f"%{city}%")
            for city in country_city_list
        ]
        base_query = base_query.filter(or_(*city_conditions))

    # Get total count
    total_count = base_query.count()

    # Apply pagination and ordering
    offset = (page - 1) * page_size
    jobs = (
        base_query.order_by(
            models.user.Job.trs_score.desc(), models.user.Job.created_at.desc()
        )
        .offset(offset)
        .limit(page_size)
        .all()
    )

    # Convert to simplified response format (only id, trs_score, permit_type, country_city, state)
    job_responses = [
        {
            "id": job.id,
            "trs_score": job.trs_score,
            "permit_type": job.permit_type,
            "country_city": job.country_city if job.country_city else [],
            "state": job.state if job.state else [],
        }
        for job in jobs
    ]

    return {
        "jobs": job_responses,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": (total_count + page_size - 1) // page_size,
    }


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
            "country_city": job.country_city,
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
            "Country/City",
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
                job.country_city,
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


@router.get("/matched-jobs-contractor", response_model=schemas.PaginatedJobResponse)
async def get_matched_jobs_contractor(
    db: Session = Depends(get_db),
    current_user: models.user.User = Depends(get_current_user),
):
    """
    Get jobs matched to contractor's selected trade categories from their profile.
    Automatically fetches trade_specialities, state, and country_city from contractor's database profile.
    Searches for keywords in permit_type and project_description columns.
    Filters jobs by contractor's state and country_city location.

    Trade Categories:
    1. General contracting & building
    2. Interior construction & finishes
    3. Electrical, low-voltage & solar
    4. Mechanical, HVAC & refrigeration
    5. Plumbing, gas & medical gas
    6. Fire protection systems
    7. Roofing, windows & exterior envelope
    8. Sitework, utilities & civil
    9. Landscaping, pools & outdoor features
    10. Environmental, abatement & hazardous materials
    11. Accessibility, elevators & conveyance
    12. Temporary works & construction support
    13. Zoning, entitlements & environmental review
    14. Occupancy, final inspections & assembly
    """

    # Check if user is a contractor
    if current_user.role != "Contractor":
        raise HTTPException(
            status_code=403,
            detail="Only contractors can access matched jobs. Please complete your contractor profile.",
        )

    # Get contractor profile
    contractor = (
        db.query(models.user.Contractor)
        .filter(models.user.Contractor.user_id == current_user.id)
        .first()
    )

    if not contractor:
        raise HTTPException(
            status_code=404,
            detail="Contractor profile not found. Please complete your contractor registration.",
        )

    if not contractor.is_completed:
        raise HTTPException(
            status_code=403,
            detail="Please complete your contractor profile before accessing matched jobs.",
        )

    # Get trade category from contractor's profile (stored as single string)
    trade_category = contractor.trade_categories

    if not trade_category:
        raise HTTPException(
            status_code=400,
            detail="No trade category found in your profile. Please update your contractor profile with a trade category.",
        )

    # Convert to list for processing (single category)
    trade_categories = [trade_category.strip()]

    # Get location from contractor's profile (now arrays)
    contractor_states = contractor.state if contractor.state else []
    contractor_country_cities = (
        contractor.country_city if contractor.country_city else []
    )

    # Validate trade categories
    valid_categories = trade_keywords.get_all_trade_categories()
    invalid_categories = [
        cat for cat in trade_categories if cat not in valid_categories
    ]

    if invalid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid trade categories in your profile: {', '.join(invalid_categories)}. Valid categories are: {', '.join(valid_categories)}",
        )

    # Build search conditions for all selected trade categories
    search_conditions = []

    for category in trade_categories:
        keywords = trade_keywords.get_keywords_for_trade(category)

        # Build OR conditions for each keyword in permit_type and project_description
        category_conditions = []
        for keyword in keywords:
            keyword_pattern = f"%{keyword}%"
            category_conditions.append(
                or_(
                    models.user.Job.permit_type.ilike(keyword_pattern),
                    models.user.Job.project_description.ilike(keyword_pattern),
                )
            )

        # Combine all keyword conditions for this category with OR
        if category_conditions:
            search_conditions.append(or_(*category_conditions))

    # Combine all category conditions with OR (job matches if it matches ANY category)
    base_query = db.query(models.user.Job)

    if search_conditions:
        base_query = base_query.filter(or_(*search_conditions))

    # Filter by contractor's states from profile (match ANY state in array)
    if contractor_states and len(contractor_states) > 0:
        state_conditions = [
            models.user.Job.state.ilike(f"%{state}%") for state in contractor_states
        ]
        base_query = base_query.filter(or_(*state_conditions))

    # Filter by contractor's country_city from profile (match ANY city/county in array)
    if contractor_country_cities and len(contractor_country_cities) > 0:
        city_conditions = [
            models.user.Job.country_city.ilike(f"%{city}%")
            for city in contractor_country_cities
        ]
        base_query = base_query.filter(or_(*city_conditions))

    # Get total count
    total_count = base_query.count()

    # Get all results, ordered by TRS score descending
    jobs = base_query.order_by(
        models.user.Job.trs_score.desc(), models.user.Job.created_at.desc()
    ).all()

    # Convert to response schema
    job_responses = []
    for job in jobs:
        # Check if current user has unlocked this job
        unlocked_lead = (
            db.query(models.user.UnlockedLead)
            .filter(
                models.user.UnlockedLead.user_id == current_user.id,
                models.user.UnlockedLead.job_id == job.id,
            )
            .first()
        )

        job_responses.append(
            schemas.JobResponse(
                id=job.id,
                permit_record_number=job.permit_record_number,
                date=job.date,
                permit_type=job.permit_type,
                project_description=job.project_description,
                job_address=job.job_address,
                job_cost=job.job_cost,
                permit_status=job.permit_status,
                email=job.email if unlocked_lead else None,
                phone_number=job.phone_number if unlocked_lead else None,
                country_city=job.country_city,
                state=job.state,
                work_type=job.work_type,
                credit_cost=job.credit_cost,
                category=job.category,
                trs_score=job.trs_score,
                is_unlocked=unlocked_lead is not None,
                created_at=job.created_at,
                updated_at=job.updated_at,
            )
        )

    return schemas.PaginatedJobResponse(
        jobs=job_responses,
        total=total_count,
        page=1,
        page_size=total_count,
        total_pages=1,
    )


@router.get("/matched-jobs-supplier", response_model=schemas.PaginatedJobResponse)
async def get_matched_jobs_supplier(
    db: Session = Depends(get_db),
    current_user: models.user.User = Depends(get_current_user),
):
    """
    Get jobs matched to supplier's product categories from their profile.
    Automatically fetches product_types, state, and country_city from supplier's database profile.
    Searches for keywords in permit_type and project_description columns.
    Filters jobs by supplier's state and country_city location.

    Product Categories:
    1. Waste hauling & sanitation
    2. Fencing, scaffolding & temporary structures
    3. Concrete, rebar & structural materials
    4. Lumber, framing & sheathing
    5. Roofing, waterproofing & insulation
    6. Windows, doors & storefronts
    7. Electrical supplies
    8. Plumbing supplies
    9. HVAC supplies
    10. Paints, coatings & chemicals
    11. Safety gear & PPE
    12. Tools & equipment rentals
    13. Landscaping & exterior materials
    """

    # Check if user is a supplier
    if current_user.role != "Supplier":
        raise HTTPException(
            status_code=403,
            detail="Only suppliers can access matched jobs. Please complete your supplier profile.",
        )

    # Get supplier profile
    supplier = (
        db.query(models.user.Supplier)
        .filter(models.user.Supplier.user_id == current_user.id)
        .first()
    )

    if not supplier:
        raise HTTPException(
            status_code=404,
            detail="Supplier profile not found. Please complete your supplier registration.",
        )

    if not supplier.is_completed:
        raise HTTPException(
            status_code=403,
            detail="Please complete your supplier profile before accessing matched jobs.",
        )

    # Get product category from supplier's profile (stored as single string)
    product_category = supplier.product_categories

    if not product_category:
        raise HTTPException(
            status_code=400,
            detail="No product category found in your profile. Please update your supplier profile with a product category.",
        )

    # Convert to list for processing (single category)
    product_categories = [product_category.strip()]

    # Get location from supplier's profile (now arrays)
    supplier_states = supplier.service_states if supplier.service_states else []
    supplier_country_cities = supplier.country_city if supplier.country_city else []

    # Validate product categories
    valid_categories = product_keywords.get_all_product_categories()
    invalid_categories = [
        cat for cat in product_categories if cat not in valid_categories
    ]

    if invalid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid product categories in your profile: {', '.join(invalid_categories)}. Valid categories are: {', '.join(valid_categories)}",
        )

    # Build search conditions for all selected product categories
    search_conditions = []

    for category in product_categories:
        keywords = product_keywords.get_keywords_for_product(category)

        # Build OR conditions for each keyword in permit_type and project_description
        category_conditions = []
        for keyword in keywords:
            keyword_pattern = f"%{keyword}%"
            category_conditions.append(
                or_(
                    models.user.Job.permit_type.ilike(keyword_pattern),
                    models.user.Job.project_description.ilike(keyword_pattern),
                )
            )

        # Combine all keyword conditions for this category with OR
        if category_conditions:
            search_conditions.append(or_(*category_conditions))

    # Combine all category conditions with OR (job matches if it matches ANY category)
    base_query = db.query(models.user.Job)

    if search_conditions:
        base_query = base_query.filter(or_(*search_conditions))

    # Filter by supplier's states from profile (match ANY state in array)
    if supplier_states and len(supplier_states) > 0:
        state_conditions = [
            models.user.Job.state.ilike(f"%{state}%") for state in supplier_states
        ]
        base_query = base_query.filter(or_(*state_conditions))

    # Filter by supplier's country_city from profile (match ANY city/county in array)
    if supplier_country_cities and len(supplier_country_cities) > 0:
        city_conditions = [
            models.user.Job.country_city.ilike(f"%{city}%")
            for city in supplier_country_cities
        ]
        base_query = base_query.filter(or_(*city_conditions))

    # Get total count
    total_count = base_query.count()

    # Get all results, ordered by TRS score descending
    jobs = base_query.order_by(
        models.user.Job.trs_score.desc(), models.user.Job.created_at.desc()
    ).all()

    # Convert to response schema
    job_responses = []
    for job in jobs:
        # Check if current user has unlocked this job
        unlocked_lead = (
            db.query(models.user.UnlockedLead)
            .filter(
                models.user.UnlockedLead.user_id == current_user.id,
                models.user.UnlockedLead.job_id == job.id,
            )
            .first()
        )

        job_responses.append(
            schemas.JobResponse(
                id=job.id,
                permit_record_number=job.permit_record_number,
                date=job.date,
                permit_type=job.permit_type,
                project_description=job.project_description,
                job_address=job.job_address,
                job_cost=job.job_cost,
                permit_status=job.permit_status,
                email=job.email if unlocked_lead else None,
                phone_number=job.phone_number if unlocked_lead else None,
                country_city=job.country_city,
                state=job.state,
                work_type=job.work_type,
                credit_cost=job.credit_cost,
                category=job.category,
                trs_score=job.trs_score,
                is_unlocked=unlocked_lead is not None,
                created_at=job.created_at,
                updated_at=job.updated_at,
            )
        )

    return schemas.PaginatedJobResponse(
        jobs=job_responses,
        total=total_count,
        page=1,
        page_size=total_count,
        total_pages=1,
    )
