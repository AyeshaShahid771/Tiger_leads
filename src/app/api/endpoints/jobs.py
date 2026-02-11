import csv
import io
import json
import logging
import base64
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Union

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, Body, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from src.app import models, schemas
from src.app.api.deps import (
    get_current_user,
    get_effective_user,
    require_admin,
    require_admin_token,
)
from src.app.core.database import get_db
from src.app.data import us_locations

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


def require_main_or_editor_for_jobs(current_user: models.User):
    """
    Helper function to check if user can perform job management actions.
    Allows:
    - Main accounts (no parent_user_id)
    - Sub-users with team_role='editor'
    
    Raises HTTPException(403) for viewers or unauthorized users.
    """
    is_main = not getattr(current_user, "parent_user_id", None)
    is_editor = (
        getattr(current_user, "parent_user_id", None) is not None
        and getattr(current_user, "team_role", None) == "editor"
    )
    
    if not (is_main or is_editor):
        raise HTTPException(
            status_code=403,
            detail="This action requires main account or editor access. Viewers have read-only permissions."
        )
    return current_user


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
    has_documents=False,  # NEW: Bonus for jobs with uploaded documents
):
    """
    Calculate Total Relevance Score (TRS) based on multiple factors.

    Scoring factors with intelligent weighting:
    - Project Value (weight: 30%)
    - Permit Stage (weight: 25%)
    - Contact Info (weight: 20%)
    - Description Quality (weight: 15%)
    - Address Completeness (weight: 10%)
    - Bonus/Penalty modifiers for combinations

    Returns: Integer score scaled to range 10-20
    """
    pv_score = project_value_score(project_value)
    st_score = stage_score(permit_status)
    ct_score = contact_score(phone_number, email)
    desc_score = description_quality_score(project_description)
    addr_score = address_completeness_score(job_address)

    # Weighted average
    base_trs = (
        (pv_score * 0.30)  # 30% weight - increased importance
        + (st_score * 0.25)  # 25% weight
        + (ct_score * 0.20)  # 20% weight
        + (desc_score * 0.15)  # 15% weight
        + (addr_score * 0.10)  # 10% weight
    )
    
    # Intelligent modifiers based on data quality combinations
    modifiers = 0
    
    # Document bonus - jobs with uploaded documents are premium quality
    # This gives contractor-uploaded jobs with docs the highest TRS (18-20 range)
    if has_documents:
        modifiers += 8  # Significant boost for documented jobs
    
    # Address length for additional variation
    address_length = len(job_address) if job_address else 0
    
    # High-value job with good contact info = +5 points
    if pv_score >= 80 and ct_score >= 80:
        modifiers += 5
    
    # Complete info (good description + address + contact) = +4 points
    if desc_score >= 70 and addr_score >= 70 and ct_score >= 50:
        modifiers += 4
    
    # Premium stage (issued/under construction) with high value = +3 points
    if st_score >= 90 and pv_score >= 70:
        modifiers += 3
    
    # Good description quality with high value = +3 points
    if desc_score >= 75 and pv_score >= 65:
        modifiers += 3
    
    # Very detailed address (80+ chars) with good data quality = +2 points
    if address_length >= 80 and addr_score >= 70:
        modifiers += 2
    
    # Complete address (50-80 chars) with some value = +1 point
    if 50 <= address_length < 80 and pv_score >= 40:
        modifiers += 1
    
    # Missing critical contact info penalty = -4 points
    if ct_score <= 10:
        modifiers -= 4
    
    # Low value with poor info = -3 points
    if pv_score <= 35 and desc_score <= 40:
        modifiers -= 3
    
    # Early stage with minimal info = -2 points
    if st_score <= 30 and (desc_score <= 45 or addr_score <= 40):
        modifiers -= 2
    
    # Very short address (< 20 chars) with low quality = -1 point
    if address_length < 20 and addr_score < 50:
        modifiers -= 1
    
    # Apply modifiers
    final_trs = base_trs + modifiers
    
    # Scale from 0-100 range to 10-20 range
    # Use non-linear scaling for better distribution
    if final_trs <= 30:
        scaled_trs = 10 + (final_trs / 30) * 2  # 10-12 range
    elif final_trs <= 50:
        scaled_trs = 12 + ((final_trs - 30) / 20) * 3  # 12-15 range
    elif final_trs <= 70:
        scaled_trs = 15 + ((final_trs - 50) / 20) * 3  # 15-18 range
    else:
        scaled_trs = 18 + ((final_trs - 70) / 30) * 2  # 18-20 range
    
    # Ensure it stays within 10-20 range
    scaled_trs = max(10, min(20, scaled_trs))
    
    return int(round(scaled_trs))


@router.post(
    "/upload-contractor-job"
)
def upload_contractor_job(
    # JSON body data
    permit_number: Optional[str] = Form(None),
    permit_status: Optional[str] = Form(None),
    permit_type_norm: Optional[str] = Form(None),
    job_address: Optional[str] = Form(None),
    project_description: Optional[str] = Form(None),
    project_cost_total: Optional[int] = Form(None),
    contractor_name: Optional[str] = Form(None),
    contractor_company: Optional[str] = Form(None),
    contractor_email: Optional[str] = Form(None),
    contractor_phone: Optional[str] = Form(None),
    source_county: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
    property_type: Optional[str] = Form(None),  # Residential or Commercial
    user_types: str = Form(...),  # JSON string: [{"user_type":"electrician","offset_days":0}]
    temp_upload_id: Optional[str] = Form(None),  # Optional: link to temp documents
    
    # Dependencies
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Allow a Contractor to upload a single job/lead manually with documents.

    Request format (multipart/form-data):
    - All job data as form fields
    - property_type: 'Residential' or 'Commercial' (optional)
    - user_types: JSON string array e.g. [{"user_type":"electrician","offset_days":0}]
    - temp_upload_id: Optional - link to previously uploaded temp documents
    
    Workflow:
    1. Upload documents via POST /jobs/upload-temp-documents (if needed)
    2. Submit job with the returned temp_upload_id (or without documents)
    
    - Creates separate job records for each user type
    - Each job has independent review status and expiration
    - All documents attached to each job record (if temp_upload_id provided)
    - Status: 'pending' (requires admin approval)
    """
    import uuid
    
    # Allow main accounts OR editors
    require_main_or_editor_for_jobs(current_user)

    # Parse user_types JSON string
    try:
        user_types_list = json.loads(user_types)
        if not user_types_list or len(user_types_list) == 0:
            raise HTTPException(
                status_code=400,
                detail="At least one user type configuration is required"
            )
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Invalid user_types format. Must be valid JSON array."
        )
    
    # Validate property_type if provided
    if property_type and property_type not in ["Residential", "Commercial"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid property_type. Must be 'Residential' or 'Commercial'."
        )

    # Retrieve documents from temp table if temp_upload_id provided
    documents = []
    
    if temp_upload_id:
        temp_doc = (
            db.query(models.user.TempDocument)
            .filter(
                models.user.TempDocument.temp_upload_id == temp_upload_id,
                models.user.TempDocument.user_id == effective_user.id
            )
            .first()
        )
        
        if not temp_doc:
            raise HTTPException(
                status_code=404,
                detail="Temporary upload not found or does not belong to you"
            )
        
        # Check if expired
        from datetime import datetime
        from zoneinfo import ZoneInfo
        est_tz = ZoneInfo("America/New_York")
        now_est = datetime.now(est_tz).replace(tzinfo=None)
        
        if now_est > temp_doc.expires_at:
            raise HTTPException(
                status_code=410,
                detail="Temporary upload has expired"
            )
        
        # Use documents from temp table
        documents = temp_doc.documents
        
        # Mark as linked to job (won't be cleaned up)
        from datetime import timedelta
        temp_doc.linked_to_job = True
        # Set expiration to 100 years in future (effectively never expires)
        temp_doc.expires_at = datetime.now() + timedelta(days=36500)
        db.commit()

    # Calculate TRS score with document bonus
    # Jobs with uploaded documents get higher TRS (18-20 range)
    has_docs = len(documents) > 0 if documents else False
    trs = calculate_trs_score(
        project_cost_total,
        permit_status,
        contractor_phone,
        contractor_email,
        project_description,
        job_address,
        has_documents=has_docs,  # Pass document flag for TRS boost
    )

    # Generate unique job_group_id to link all records from this submission
    job_group_id = f"JG-{uuid.uuid4().hex[:12].upper()}"
    
    created_jobs = []
    
    # Create separate job record for each user type
    for user_type_config in user_types_list:
        job = models.user.Job(
            # Job details - same for all user types
            permit_number=permit_number,
            permit_type_norm=permit_type_norm,
            project_description=project_description,
            job_address=job_address,
            property_type=property_type,
            project_cost_total=project_cost_total,
            permit_status=permit_status,
            contractor_email=contractor_email,
            contractor_phone=contractor_phone,
            source_county=source_county,
            state=state,
            contractor_name=contractor_name,
            contractor_company=contractor_company,
            
            # User type specific
            audience_type_slugs=user_type_config.get("user_type"),
            day_offset=user_type_config.get("offset_days", 0),
            
            # Documents (same for all user types)
            job_documents=documents if documents else None,
            
            # Common metadata
            trs_score=trs,
            uploaded_by_contractor=True,
            uploaded_by_user_id=effective_user.id,
            job_review_status="pending",
            job_group_id=job_group_id,
        )
        
        db.add(job)
        created_jobs.append(job)
    
    db.commit()
    
    # Refresh all jobs to get their IDs
    for job in created_jobs:
        db.refresh(job)
    
    # Return response with first job info
    return {
        "message": f"Successfully created {len(created_jobs)} job record(s)",
        "job_group_id": job_group_id,
        "jobsproperty_type": created_jobs[0].property_type,
            "_created": len(created_jobs),
        "documents_uploaded": len(documents),
        "job_ids": [job.id for job in created_jobs],
        "sample_job": {
            "id": created_jobs[0].id,
            "permit_number": created_jobs[0].permit_number,
            "job_address": created_jobs[0].job_address,
            "contractor_name": contractor_name,
            "contractor_company": contractor_company,
            "status": created_jobs[0].job_review_status,
        }
    }


@router.post(
    "/save-draft"
)
def save_draft_job(
    # JSON body data
    permit_number: Optional[str] = Form(None),
    permit_status: Optional[str] = Form(None),
    permit_type_norm: Optional[str] = Form(None),
    job_address: Optional[str] = Form(None),
    project_description: Optional[str] = Form(None),
    project_cost_total: Optional[int] = Form(None),
    contractor_name: Optional[str] = Form(None),
    contractor_company: Optional[str] = Form(None),
    contractor_email: Optional[str] = Form(None),
    contractor_phone: Optional[str] = Form(None),
    source_county: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
    user_types: Optional[str] = Form(None),  # JSON string: [{"user_type":"electrician","offset_days":0}]
    temp_upload_id: Optional[str] = Form(None),  # Optional: link to temp documents
    
    # Dependencies
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Save a job as draft for later completion/submission.
    
    Request format (multipart/form-data):
    - All job data as optional form fields
    - user_types: Optional JSON string array e.g. [{"user_type":"electrician","offset_days":0}]
    - temp_upload_id: Optional - link to previously uploaded temp documents
    
    Draft workflow:
    1. Upload documents via POST /jobs/upload-temp-documents (if needed)
    2. Save draft with the returned temp_upload_id (all fields optional)
    3. Temp documents remain linked to draft and won't be deleted
    4. Later: submit draft as actual job via POST /jobs/upload-contractor-job
    """
    
    # Allow main accounts OR editors
    require_main_or_editor_for_jobs(current_user)

    # Parse user_types JSON string if provided
    user_types_parsed = None
    if user_types:
        try:
            user_types_parsed = json.loads(user_types)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Invalid user_types format. Must be valid JSON array."
            )

    # If temp_upload_id provided, mark it as linked to draft
    if temp_upload_id:
        temp_doc = (
            db.query(models.user.TempDocument)
            .filter(
                models.user.TempDocument.temp_upload_id == temp_upload_id,
                models.user.TempDocument.user_id == effective_user.id
            )
            .first()
        )
        
        if temp_doc:
            # Mark as linked to draft (won't be cleaned up)
            from datetime import timedelta
            temp_doc.linked_to_draft = True
            # Set expiration to 100 years in future (effectively never expires)
            temp_doc.expires_at = datetime.now() + timedelta(days=36500)
            db.commit()
    
    # Create draft job record
    draft_job = models.user.DraftJob(
        user_id=effective_user.id,
        permit_number=permit_number,
        permit_type_norm=permit_type_norm,
        project_description=project_description,
        job_address=job_address,
        project_cost_total=project_cost_total,
        permit_status=permit_status,
        contractor_email=contractor_email,
        contractor_phone=contractor_phone,
        source_county=source_county,
        state=state,
        contractor_name=contractor_name,
        contractor_company=contractor_company,
        user_types=user_types_parsed,
        temp_upload_id=temp_upload_id,
    )
    
    db.add(draft_job)
    db.commit()
    db.refresh(draft_job)
    
    return {
        "message": "Draft saved successfully",
        "draft_id": draft_job.id,
        "temp_upload_id": temp_upload_id,
        "has_documents": temp_upload_id is not None,
        "created_at": draft_job.created_at.isoformat() if draft_job.created_at else None,
    }


@router.post(
    "/publish-draft/{draft_id}"
)
def publish_draft_job(
    draft_id: int,
    delete_draft: bool = False,  # Optional: delete draft after publishing
    
    # Dependencies
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Publish a draft job to create actual job records.
    
    Takes a draft_id and creates job records in the jobs table,
    exactly like the upload-contractor-job endpoint does.
    
    Path parameters:
    - draft_id: ID of the draft to publish
    
    Query parameters:
    - delete_draft: If true, delete the draft after successful publishing (default: false)
    
    Returns:
    - Same response as upload-contractor-job endpoint
    """
    import uuid
    
    # Allow main accounts OR editors
    require_main_or_editor_for_jobs(current_user)

    # Get the draft job
    draft = (
        db.query(models.user.DraftJob)
        .filter(
            models.user.DraftJob.id == draft_id,
            models.user.DraftJob.user_id == effective_user.id
        )
        .first()
    )
    
    if not draft:
        raise HTTPException(
            status_code=404,
            detail="Draft not found or does not belong to you"
        )
    
    # Validate that user_types is provided
    if not draft.user_types or len(draft.user_types) == 0:
        raise HTTPException(
            status_code=400,
            detail="Draft must have at least one user type configuration to publish"
        )

    # Retrieve documents from temp table if temp_upload_id provided
    documents = []
    
    if draft.temp_upload_id:
        temp_doc = (
            db.query(models.user.TempDocument)
            .filter(
                models.user.TempDocument.temp_upload_id == draft.temp_upload_id,
                models.user.TempDocument.user_id == effective_user.id
            )
            .first()
        )
        
        if not temp_doc:
            raise HTTPException(
                status_code=404,
                detail="Temporary documents not found"
            )
        
        # Check if expired (but allow if already linked to draft)
        from datetime import datetime
        from zoneinfo import ZoneInfo
        est_tz = ZoneInfo("America/New_York")
        now_est = datetime.now(est_tz).replace(tzinfo=None)
        
        if not temp_doc.linked_to_draft and now_est > temp_doc.expires_at:
            raise HTTPException(
                status_code=410,
                detail="Temporary upload has expired"
            )
        
        # Use documents from temp table
        documents = temp_doc.documents
        
        # Mark as linked to job (won't be cleaned up)
        from datetime import timedelta
        temp_doc.linked_to_job = True
        # Set expiration to 100 years in future (effectively never expires)
        temp_doc.expires_at = datetime.now() + timedelta(days=36500)
        db.commit()

    # Calculate TRS score
    trs = calculate_trs_score(
        draft.project_cost_total,
        draft.permit_status,
        draft.contractor_phone,
        draft.contractor_email,
        draft.project_description,
        draft.job_address,
    )

    # Generate unique job_group_id to link all records from this submission
    job_group_id = f"JG-{uuid.uuid4().hex[:12].upper()}"
    
    created_jobs = []
    
    # Create separate job record for each user type
    for user_type_config in draft.user_types:
        job = models.user.Job(
            # Job details - same for all user types
            permit_number=draft.permit_number,
            permit_type_norm=draft.permit_type_norm,
            project_description=draft.project_description,
            job_address=draft.job_address,
            project_cost_total=draft.project_cost_total,
            permit_status=draft.permit_status,
            contractor_email=draft.contractor_email,
            contractor_phone=draft.contractor_phone,
            source_county=draft.source_county,
            state=draft.state,
            contractor_name=draft.contractor_name,
            contractor_company=draft.contractor_company,
            
            # User type specific
            audience_type_slugs=user_type_config.get("user_type"),
            day_offset=user_type_config.get("offset_days", 0),
            
            # Documents (same for all user types)
            job_documents=documents if documents else None,
            
            # Common metadata
            trs_score=trs,
            uploaded_by_contractor=True,
            uploaded_by_user_id=effective_user.id,
            job_review_status="pending",
            job_group_id=job_group_id,
        )
        
        db.add(job)
        created_jobs.append(job)
    
    db.commit()
    
    # Refresh all jobs to get their IDs
    for job in created_jobs:
        db.refresh(job)
    
    # Optionally delete the draft after successful publishing
    if delete_draft:
        db.delete(draft)
        db.commit()
    
    # Return response with first job info
    return {
        "message": f"Successfully published draft and created {len(created_jobs)} job record(s)",
        "draft_id": draft_id,
        "draft_deleted": delete_draft,
        "job_group_id": job_group_id,
        "jobs_created": len(created_jobs),
        "documents_uploaded": len(documents),
        "job_ids": [job.id for job in created_jobs],
        "sample_job": {
            "id": created_jobs[0].id,
            "permit_number": created_jobs[0].permit_number,
            "job_address": created_jobs[0].job_address,
            "contractor_name": draft.contractor_name,
            "contractor_company": draft.contractor_company,
            "status": created_jobs[0].job_review_status,
        }
    }


@router.get(
    "/my-draft-jobs"
)
def get_my_draft_jobs(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Get all draft jobs saved by the current contractor.
    
    Returns all drafts with their details including:
    - Draft ID and timestamps
    - All job fields
    - User types configuration
    - Whether documents are attached (temp_upload_id)
    """
    # Allow all users (including viewers) to view drafts

    # Return drafts for the effective (main) account so sub-accounts see the same data
    drafts = (
        db.query(models.user.DraftJob)
        .filter(models.user.DraftJob.user_id == effective_user.id)
        .order_by(models.user.DraftJob.updated_at.desc())
        .all()
    )
    
    # Format response
    draft_list = []
    for draft in drafts:
        draft_list.append({
            "draft_id": draft.id,
            "permit_number": draft.permit_number,
            "permit_type_norm": draft.audience_type_names,  # Use audience_type_names for human-readable format
            "permit_status": draft.permit_status,
            "project_description": draft.project_description,
            "job_address": draft.job_address,
            "project_cost_total": draft.project_cost_total,
            "contractor_name": draft.contractor_name,
            "contractor_company": draft.contractor_company,
            "contractor_email": draft.contractor_email,
            "contractor_phone": draft.contractor_phone,
            "source_county": draft.source_county,
            "state": draft.state,
            "user_types": draft.user_types,
            "temp_upload_id": draft.temp_upload_id,
            "has_documents": draft.temp_upload_id is not None,
            "created_at": draft.created_at.isoformat() if draft.created_at else None,
            "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
        })
    
    return {
        "total_drafts": len(draft_list),
        "drafts": draft_list
    }


@router.get(
    "/draft/{draft_id}"
)
def get_draft_detail(
    draft_id: int,
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Get detailed information about a specific draft job.
    
    Returns:
    - All draft fields
    - Document details if temp_upload_id exists
    - Document count and metadata
    """
    # Allow all users (including viewers) to view draft details

    # Get the draft
    draft = (
        db.query(models.user.DraftJob)
        .filter(
            models.user.DraftJob.id == draft_id,
            models.user.DraftJob.user_id == effective_user.id
        )
        .first()
    )
    
    if not draft:
        raise HTTPException(
            status_code=404,
            detail="Draft not found or does not belong to you"
        )
    
    # Get document details if temp_upload_id exists
    documents_info = None
    if draft.temp_upload_id:
        temp_doc = (
            db.query(models.user.TempDocument)
            .filter(
                models.user.TempDocument.temp_upload_id == draft.temp_upload_id,
                models.user.TempDocument.user_id == effective_user.id
            )
            .first()
        )
        
        if temp_doc:
            from io import BytesIO
            from PIL import Image
            
            # Generate thumbnails for all documents
            documents_with_thumbnails = []
            
            for doc in (temp_doc.documents or []):
                doc_id = doc.get("document_id", "unknown")
                filename = doc.get("filename", "unknown")
                content_type = doc.get("content_type", "unknown")
                
                thumbnail_base64 = None
                page_count = None
                
                try:
                    # Decode base64 data
                    file_data = base64.b64decode(doc["data"])
                    
                    # Handle PDFs
                    if content_type == "application/pdf":
                        try:
                            import fitz  # PyMuPDF
                            
                            # Open PDF from bytes
                            pdf_document = fitz.open(stream=file_data, filetype="pdf")
                            page_count = len(pdf_document)
                            
                            # Get first page
                            first_page = pdf_document[0]
                            
                            # Render page to image (2.0x = 144 DPI)
                            mat = fitz.Matrix(2.0, 2.0)
                            pix = first_page.get_pixmap(matrix=mat)
                            
                            # Convert pixmap to PIL Image
                            img_data = pix.tobytes("png")
                            img = Image.open(BytesIO(img_data))
                            
                            # Resize to thumbnail (max 800px)
                            img.thumbnail((800, 800), Image.Resampling.LANCZOS)
                            
                            # Convert to PNG base64
                            buffer = BytesIO()
                            img.save(buffer, format="PNG")
                            thumbnail_base64 = f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode('utf-8')}"
                            
                            pdf_document.close()
                            
                        except Exception as e:
                            logger.error(f"Error generating PDF thumbnail for {filename}: {str(e)}")
                            # Fallback: return full PDF data
                            thumbnail_base64 = f"data:application/pdf;base64,{doc['data']}"
                    
                    # Handle images
                    elif content_type in ["image/jpeg", "image/jpg", "image/png"]:
                        try:
                            img = Image.open(BytesIO(file_data))
                            
                            # Resize to thumbnail (max 800px)
                            img.thumbnail((800, 800), Image.Resampling.LANCZOS)
                            
                            # Convert to PNG base64
                            buffer = BytesIO()
                            img.save(buffer, format="PNG")
                            thumbnail_base64 = f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode('utf-8')}"
                            
                        except Exception as e:
                            logger.error(f"Error generating image thumbnail for {filename}: {str(e)}")
                
                except Exception as e:
                    logger.error(f"Error processing document {doc_id}: {str(e)}")
                
                # Add document with thumbnail
                documents_with_thumbnails.append({
                    "document_id": doc.get("document_id"),
                    "thumbnail": thumbnail_base64,
                    "filename": filename,
                    "contentType": content_type,
                    "fileSize": doc.get("size"),
                    "pageCount": page_count,
                })
            
            documents_info = {
                "temp_upload_id": temp_doc.temp_upload_id,
                "document_count": len(temp_doc.documents) if temp_doc.documents else 0,
                "documents": documents_with_thumbnails,
                "linked_to_job": temp_doc.linked_to_job,
                "linked_to_draft": temp_doc.linked_to_draft,
                "expires_at": temp_doc.expires_at.isoformat() if temp_doc.expires_at else None,
                "created_at": temp_doc.created_at.isoformat() if temp_doc.created_at else None,
            }
    
    return {
        "draft_id": draft.id,
        "permit_number": draft.permit_number,
        "permit_type_norm": draft.audience_type_names,  # Use audience_type_names for human-readable format
        "permit_status": draft.permit_status,
        "project_description": draft.project_description,
        "job_address": draft.job_address,
        "project_cost_total": draft.project_cost_total,
        "contractor_name": draft.contractor_name,
        "contractor_company": draft.contractor_company,
        "contractor_email": draft.contractor_email,
        "contractor_phone": draft.contractor_phone,
        "source_county": draft.source_county,
        "state": draft.state,
        "user_types": draft.user_types,
        "temp_upload_id": draft.temp_upload_id,
        "documents": documents_info,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
    }


@router.patch(
    "/draft/{draft_id}"
)
def update_draft_job(
    draft_id: int,
    # JSON body data - all optional
    permit_number: Optional[str] = Form(None),
    permit_status: Optional[str] = Form(None),
    permit_type_norm: Optional[str] = Form(None),
    job_address: Optional[str] = Form(None),
    project_description: Optional[str] = Form(None),
    project_cost_total: Optional[int] = Form(None),
    contractor_name: Optional[str] = Form(None),
    contractor_company: Optional[str] = Form(None),
    contractor_email: Optional[str] = Form(None),
    contractor_phone: Optional[str] = Form(None),
    source_county: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
    user_types: Optional[str] = Form(None),  # JSON string: [{"user_type":"electrician","offset_days":0}]
    
    # Dependencies
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Update an existing draft job (except documents).
    
    Path parameters:
    - draft_id: ID of the draft to update
    
    Request format (multipart/form-data):
    - All job data as optional form fields
    - user_types: Optional JSON string array e.g. [{"user_type":"electrician","offset_days":0}]
    - Only provided fields will be updated
    - Documents are NOT updated via this endpoint (use temp_upload_id workflow)
    
    Returns:
    - Updated draft information
    """
    
    # Allow main accounts OR editors
    require_main_or_editor_for_jobs(current_user)

    # Get the draft job
    draft = (
        db.query(models.user.DraftJob)
        .filter(
            models.user.DraftJob.id == draft_id,
            models.user.DraftJob.user_id == effective_user.id
        )
        .first()
    )
    
    if not draft:
        raise HTTPException(
            status_code=404,
            detail="Draft not found or does not belong to you"
        )

    # Parse user_types JSON string if provided
    user_types_parsed = None
    if user_types is not None:
        try:
            user_types_parsed = json.loads(user_types)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Invalid user_types format. Must be valid JSON array."
            )

    # Update only provided fields
    if permit_number is not None:
        draft.permit_number = permit_number
    if permit_status is not None:
        draft.permit_status = permit_status
    if permit_type_norm is not None:
        draft.permit_type_norm = permit_type_norm
    if job_address is not None:
        draft.job_address = job_address
    if project_description is not None:
        draft.project_description = project_description
    if project_cost_total is not None:
        draft.project_cost_total = project_cost_total
    if contractor_name is not None:
        draft.contractor_name = contractor_name
    if contractor_company is not None:
        draft.contractor_company = contractor_company
    if contractor_email is not None:
        draft.contractor_email = contractor_email
    if contractor_phone is not None:
        draft.contractor_phone = contractor_phone
    if source_county is not None:
        draft.source_county = source_county
    if state is not None:
        draft.state = state
    if user_types_parsed is not None:
        draft.user_types = user_types_parsed
    
    db.commit()
    db.refresh(draft)
    
    return {
        "message": "Draft updated successfully",
        "draft_id": draft.id,
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
    }


@router.delete(
    "/draft/{draft_id}"
)
def delete_draft_job(
    draft_id: int,
    delete_documents: bool = Query(True, description="Also delete associated temp documents"),
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Delete a draft job and optionally its associated temp documents.
    
    Path parameters:
    - draft_id: ID of the draft to delete
    
    Query parameters:
    - delete_documents: If true (default), also delete associated temp documents
    
    Returns information about deleted draft and documents.
    """
    
    # Allow main accounts OR editors
    require_main_or_editor_for_jobs(current_user)

    # Get the draft job
    draft = (
        db.query(models.user.DraftJob)
        .filter(
            models.user.DraftJob.id == draft_id,
            models.user.DraftJob.user_id == effective_user.id
        )
        .first()
    )
    
    if not draft:
        raise HTTPException(
            status_code=404,
            detail="Draft not found or does not belong to you"
        )
    
    temp_upload_id = draft.temp_upload_id
    documents_deleted = False
    document_count = 0
    
    # Delete associated temp documents if requested
    if delete_documents and temp_upload_id:
        temp_doc = (
            db.query(models.user.TempDocument)
            .filter(
                models.user.TempDocument.temp_upload_id == temp_upload_id,
                models.user.TempDocument.user_id == effective_user.id
            )
            .first()
        )
        
        if temp_doc:
            document_count = len(temp_doc.documents) if temp_doc.documents else 0
            db.delete(temp_doc)
            documents_deleted = True
    
    # Delete the draft
    db.delete(draft)
    db.commit()
    
    return {
        "message": "Draft deleted successfully",
        "draft_id": draft_id,
        "temp_upload_id": temp_upload_id,
        "documents_deleted": documents_deleted,
        "document_count": document_count,
    }


@router.delete(
    "/job/{job_id}"
)
def delete_uploaded_job(
    job_id: int,
    delete_documents: bool = Query(True, description="Also delete associated temp documents"),
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Delete an uploaded job and optionally its associated temp documents.
    
    Only allows deletion of jobs that were uploaded by the current contractor
    and have not been approved/posted yet (pending or declined status).
    
    Path parameters:
    - job_id: ID of the job to delete
    
    Query parameters:
    - delete_documents: If true (default), also delete associated temp documents
    
    Returns information about deleted job and documents.
    """
    
    # Allow main accounts OR editors
    require_main_or_editor_for_jobs(current_user)

    # Get the job
    job = (
        db.query(models.user.Job)
        .filter(
            models.user.Job.id == job_id,
            models.user.Job.uploaded_by_contractor.is_(True),
            models.user.Job.uploaded_by_user_id == effective_user.id
        )
        .first()
    )
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found or does not belong to you"
        )
    
    # Only allow deletion of pending or declined jobs
    if job.job_review_status not in ["pending", "declined"]:
        raise HTTPException(
            status_code=403,
            detail=f"Cannot delete jobs with status '{job.job_review_status}'. Only 'pending' or 'declined' jobs can be deleted."
        )
    
    job_group_id = job.job_group_id
    documents_deleted = False
    document_count = 0
    temp_upload_id = None
    
    # Find temp documents associated with this job group
    # Look for temp documents that were used for this job submission
    if delete_documents and job.job_documents:
        # Try to find the temp document by matching document IDs
        for doc in job.job_documents:
            doc_id = doc.get("document_id")
            if doc_id:
                # Find temp document containing this document ID
                temp_docs = (
                    db.query(models.user.TempDocument)
                    .filter(models.user.TempDocument.user_id == effective_user.id)
                    .all()
                )
                
                for temp_doc in temp_docs:
                    if temp_doc.documents:
                        doc_ids = [d.get("document_id") for d in temp_doc.documents]
                        if doc_id in doc_ids:
                            temp_upload_id = temp_doc.temp_upload_id
                            document_count = len(temp_doc.documents)
                            db.delete(temp_doc)
                            documents_deleted = True
                            break
                
                if documents_deleted:
                    break
    
    # Delete all jobs in the same job group
    jobs_in_group = (
        db.query(models.user.Job)
        .filter(
            models.user.Job.job_group_id == job_group_id,
            models.user.Job.uploaded_by_user_id == effective_user.id
        )
        .all()
    )
    
    jobs_deleted = len(jobs_in_group)
    
    for j in jobs_in_group:
        db.delete(j)
    
    db.commit()
    
    return {
        "message": "Job(s) deleted successfully",
        "job_id": job_id,
        "job_group_id": job_group_id,
        "jobs_deleted": jobs_deleted,
        "temp_upload_id": temp_upload_id,
        "documents_deleted": documents_deleted,
        "document_count": document_count,
    }


@router.get(
    "/my-uploaded-jobs",
    response_model=List[schemas.subscription.JobDetailResponse],
)
def get_my_uploaded_jobs(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Get all jobs uploaded by the current contractor, including their review status.
    
    Returns all uploaded jobs without deduplication (each audience variant is returned).
    Each job includes:
    - job_review_status: The review status of the job (pending, posted, declined)
    - property_type: The property type (Residential or Commercial)
    - All other job fields from JobDetailResponse schema
    """
    # Allow all users (including viewers) to view uploaded jobs

    # Return jobs for the effective (main) account so sub-accounts see the same data
    # Do NOT deduplicate - return all jobs including each audience variant
    all_jobs = (
        db.query(models.user.Job)
        .filter(
            models.user.Job.uploaded_by_contractor.is_(True),
            models.user.Job.uploaded_by_user_id == effective_user.id,
        )
        .order_by(models.user.Job.created_at.desc())
        .all()
    )
    # Return all uploaded jobs (do not deduplicate so each audience variant is returned)
    # Each job includes job_review_status and property_type fields
    logger.info(f"/my-uploaded-jobs: returning {len(all_jobs)} uploaded jobs for user {effective_user.id}")

    return all_jobs


@router.get(
    "/by-status",
    response_model=List[schemas.subscription.JobDetailResponse],
)
def get_jobs_by_status(
    status: str = Query(
        ...,
        description="Job review status to filter by (pending, posted, declined)",
    ),
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Get all jobs by `job_review_status` (e.g., pending, posted, declined).

    Intended for admin/moderation dashboards to review contractor-uploaded jobs.
    """
    allowed_statuses = {"pending", "posted", "declined"}
    if status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Allowed values: {', '.join(sorted(allowed_statuses))}",
        )

    # Allow all users (including viewers) to query jobs by status

    # Limit to jobs belonging to the effective (main) account so sub-accounts see the same data
    all_jobs = (
        db.query(models.user.Job)
        .filter(
            models.user.Job.job_review_status == status,
            models.user.Job.uploaded_by_user_id == effective_user.id,
        )
        .order_by(models.user.Job.created_at.desc())
        .all()
    )
    
    # Deduplicate jobs
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
    
    logger.info(f"/by-status ({status}): {len(all_jobs)} jobs → {len(deduplicated_jobs)} unique ({len(all_jobs) - len(deduplicated_jobs)} duplicates removed)")

    return deduplicated_jobs


@router.post("/upload-leads", response_model=schemas.subscription.BulkUploadResponse)
async def upload_leads_file(
    file: UploadFile = File(..., description="JSON, CSV, or Excel file containing job/lead data"),
    admin: models.user.AdminUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Bulk upload leads/jobs from file (multipart/form-data).

    Accepts:
    - JSON file (.json)
    - CSV file (.csv)
    - Excel file (.xlsx, .xls)

    Expected fields:
    - queue_id, rule_id, recipient_group, recipient_group_id
    - day_offset, anchor_event, anchor_at, due_at
    - permit_id, permit_number, permit_status, permit_type_norm
    - job_address, project_description, project_cost_total, project_cost_source
    - source_county, source_system, routing_anchor_at
    - first_seen_at, last_seen_at
    - contractor_name, contractor_company, contractor_email, contractor_phone
    - audience_type_slugs, audience_type_names, state, querystring
    - trs_score (automatically calculated)

    Admin users with role 'admin' or 'editor' only.
    """
    try:
        # Validate file type
        allowed_extensions = [".json", ".csv", ".xlsx", ".xls"]
        file_ext = f".{file.filename.lower().split('.')[-1]}"
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail="Invalid file format. Only JSON, CSV and Excel files (.json, .csv, .xlsx, .xls) are supported.",
            )

        # Read file content
        contents = await file.read()
        df = None

        # Parse file based on extension
        if file_ext == ".json":
            try:
                data = json.loads(contents.decode('utf-8'))
                # Convert single object to list
                if isinstance(data, dict):
                    data = [data]
                df = pd.DataFrame(data)
            except json.JSONDecodeError as e:
                raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
        elif file_ext == ".csv":
            df = pd.read_csv(io.BytesIO(contents))
        else:  # .xlsx or .xls
            df = pd.read_excel(io.BytesIO(contents))

        total_rows = len(df)
        successful = 0
        failed = 0
        errors = []
        created_jobs = []  # Collect created job objects

        # Normalize column names
        df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')

        # Process each row
        for index, row in df.iterrows():
            try:
                # Helper to get value
                def get_value(field_name, default=None):
                    if field_name in df.columns and pd.notna(row.get(field_name)):
                        return row.get(field_name)
                    return default

                # Parse datetime fields
                def parse_datetime(value):
                    if not value or pd.isna(value):
                        return None
                    try:
                        # Handle both timestamp and string formats
                        parsed = pd.to_datetime(value)
                        # Convert to python datetime if it's a pandas Timestamp
                        if hasattr(parsed, 'to_pydatetime'):
                            return parsed.to_pydatetime()
                        return parsed
                    except Exception as e:
                        logger.warning(f"Failed to parse datetime '{value}': {str(e)}")
                        return None

                # Create job object with new schema
                # Calculate TRS score based on available data
                trs = calculate_trs_score(
                    project_value=get_value('project_cost_total'),
                    permit_status=get_value('permit_status'),
                    phone_number=get_value('contractor_phone'),
                    email=get_value('contractor_email'),
                    project_description=get_value('project_description'),
                    job_address=get_value('job_address'),
                    has_documents=False  # Bulk uploads don't support documents
                )
                
                # Calculate job_review_status based on timing
                anchor_at = parse_datetime(get_value('anchor_at'))
                due_at = parse_datetime(get_value('due_at'))
                day_offset = int(get_value('day_offset', 0))
                
                job_review_status = "pending"  # Default
                review_posted_at = None
                now = datetime.utcnow()
                
                # Simplified logic: only "posted" or "pending"
                if anchor_at and due_at:
                    posting_time = anchor_at + timedelta(days=day_offset)
                    
                    # If current time >= posting_time OR due_at has passed → posted
                    if now >= posting_time or now > due_at:
                        job_review_status = "posted"
                        review_posted_at = now
                        logger.info(f"Row {index + 2}: Posted (now {now}, posting_time {posting_time}, due_at {due_at})")
                    # Otherwise → pending (offset days remaining)
                    else:
                        job_review_status = "pending"
                        logger.info(f"Row {index + 2}: Pending (now {now}, posting_time {posting_time})")
                elif due_at:
                    # Has due_at but no anchor_at - check if due_at passed
                    if now > due_at:
                        job_review_status = "posted"
                        review_posted_at = now
                        logger.info(f"Row {index + 2}: Posted (due_at passed)")
                    else:
                        job_review_status = "pending"
                        logger.info(f"Row {index + 2}: Pending (no anchor_at)")
                else:
                    # No timing info - default to pending
                    job_review_status = "pending"
                    logger.info(f"Row {index + 2}: Pending (no timing info)")


                
                # Helper function to safely convert to int
                def safe_int(value):
                    if value is None or (isinstance(value, str) and not value.strip()):
                        return None
                    try:
                        return int(value)
                    except (ValueError, TypeError):
                        return None
                
                # Helper function to safely convert to string (returns None for null/empty)
                def safe_str(value):
                    if value is None:
                        return None
                    val_str = str(value).strip()
                    return val_str if val_str else None
                
                # Process permit_type_norm: remove "permit" from end and add "project"
                permit_type_raw = safe_str(get_value('permit_type_norm'))
                if permit_type_raw:
                    # Remove "permit" from end if exists (case insensitive)
                    if permit_type_raw.lower().endswith(' permit'):
                        permit_type_raw = permit_type_raw[:-7].strip()  # Remove " permit"
                    elif permit_type_raw.lower().endswith('permit'):
                        permit_type_raw = permit_type_raw[:-6].strip()  # Remove "permit"
                    # Add "project" at the end
                    permit_type_normalized = f"{permit_type_raw} Project"
                else:
                    permit_type_normalized = None
                
                job = models.user.Job(
                    queue_id=safe_int(get_value('queue_id')),
                    rule_id=safe_int(get_value('rule_id')),
                    recipient_group=safe_str(get_value('recipient_group')),
                    recipient_group_id=safe_int(get_value('recipient_group_id')),
                    day_offset=day_offset,
                    anchor_event=safe_str(get_value('anchor_event')),
                    anchor_at=anchor_at,
                    due_at=due_at,
                    permit_id=safe_int(get_value('permit_id')),
                    # Direct mapping from input fields
                    permit_number=safe_str(get_value('project_number')),  # From project_number
                    permit_status=safe_str(get_value('permit_project_status')),  # From permit_project_status
                    permit_type_norm=permit_type_normalized,
                    job_address=safe_str(get_value('project_address')),  # From project_address
                    project_description=safe_str(get_value('project_description')),
                    project_cost_total=safe_int(get_value('project_cost')),  # From project_cost,
                    project_cost_source=safe_str(get_value('project_cost_source')),
                    source_county=safe_str(get_value('source_county')),
                    source_system=safe_str(get_value('source_system')),
                    routing_anchor_at=parse_datetime(get_value('routing_anchor_at')),
                    first_seen_at=parse_datetime(get_value('first_seen_at')),
                    last_seen_at=parse_datetime(get_value('last_seen_at')),
                    contractor_name=safe_str(get_value('contractor_name')),
                    contractor_company=safe_str(get_value('contractor_company')),
                    contractor_email=safe_str(get_value('contractor_email')),
                    contractor_phone=safe_str(get_value('contractor_phone')),
                    audience_type_slugs=safe_str(get_value('audience_type_slugs')),
                    audience_type_names=safe_str(get_value('audience_type_names')),
                    state=safe_str(get_value('state')),
                    querystring=safe_str(get_value('querystring')),
                    trs_score=trs,
                    uploaded_by_contractor=False,
                    uploaded_by_user_id=None,
                    job_review_status=job_review_status,
                    review_posted_at=review_posted_at,
                    # New fields for enhanced project data
                    project_number=safe_str(get_value('project_number')),
                    project_type=safe_str(get_value('project_type')),
                    project_sub_type=safe_str(get_value('project_sub_type')),
                    project_status=safe_str(get_value('permit_project_status')),  # Maps from permit_project_status
                    project_cost=safe_int(get_value('project_cost')),
                    project_address=safe_str(get_value('project_address')),
                    owner_name=safe_str(get_value('owner_name')),
                    applicant_name=safe_str(get_value('applicant_name')),
                    applicant_email=safe_str(get_value('applicant_email')),
                    applicant_phone=safe_str(get_value('applicant_phone')),
                    contractor_company_and_address=safe_str(get_value('contractor_company_and_address')),
                    permit_raw=safe_str(get_value('permit_raw')),
                )

                db.add(job)
                created_jobs.append(job)  # Collect job for ID retrieval
                successful += 1

            except Exception as e:
                failed += 1
                errors.append(f"Row {index + 2}: {str(e)}")
                logger.error(f"Error processing row {index + 2}: {str(e)}")

        # Commit all successful inserts
        db.commit()
        
        # Refresh all jobs to get their auto-generated IDs
        for job in created_jobs:
            db.refresh(job)

        logger.info(
            f"Bulk upload completed: {successful} successful, {failed} failed out of {total_rows} total"
        )

        return {
            "total_rows": total_rows,
            "successful": successful,
            "failed": failed,
            "errors": errors[:50],  # Return first 50 errors
            "job_ids": [job.id for job in created_jobs],  # Return IDs of created jobs
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error during bulk upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")


@router.post("/upload-leads-json", response_model=schemas.subscription.BulkUploadResponse)
async def upload_leads_json(
    body: Union[dict, List[dict]] = Body(
        ...,
        example=[
            {
                "queue_id": 11,
                "rule_id": 26,
                "recipient_group": "erosion",
                "recipient_group_id": 75,
                "day_offset": 0,
                "anchor_event": "SUBMITTED",
                "anchor_at": "2025-12-31 22:32:13",
                "due_at": "2025-12-31 22:32:13",
                "permit_id": 120,
                "permit_number": "RES-NEW-25-002742",
                "permit_status": "Ready to Issue",
                "permit_type_norm": "single_family_residential_building_permit",
                "job_address": "3324 CONNECTICUT AV",
                "project_description": "Connecticut TH Project NEW",
                "project_cost_total": 300000,
                "project_cost_source": "general_project_information",
                "source_county": "Mecklenburg County",
                "source_system": "Accela",
                "routing_anchor_at": "2025-12-31 22:32:13",
                "first_seen_at": "2025-12-31 22:32:13",
                "last_seen_at": "2025-12-31 22:32:13",
                "contractor_name": "Nate Hill",
                "contractor_company": None,
                "contractor_email": "nate@hallmarkbuilding.com",
                "contractor_phone": "9108996399",
                "audience_type_slugs": "erosion_materials",
                "audience_type_names": "Erosion materials",
                "state": "",
                "querystring": ""
            },
            {
                "queue_id": 1,
                "rule_id": 2,
                "recipient_group": "site_prep",
                "recipient_group_id": 51,
                "day_offset": 0,
                "anchor_event": "SUBMITTED",
                "anchor_at": "2025-12-31 22:32:13",
                "due_at": "2025-12-31 22:32:13",
                "permit_id": 121,
                "permit_number": "RES-NEW-25-002743",
                "permit_status": "Ready to Issue",
                "permit_type_norm": "single_family_residential_building_permit",
                "job_address": "1234 MAIN ST",
                "project_description": "Main St TH Project NEW",
                "project_cost_total": 250000,
                "project_cost_source": "general_project_information",
                "source_county": "Mecklenburg County",
                "source_system": "Accela",
                "routing_anchor_at": "2025-12-31 22:32:13",
                "first_seen_at": "2025-12-31 22:32:13",
                "last_seen_at": "2025-12-31 22:32:13",
                "contractor_name": "Jane Smith",
                "contractor_company": "Smith Builders",
                "contractor_email": "jane@smithbuilders.com",
                "contractor_phone": "9805551234",
                "audience_type_slugs": "erosion_control_contractor,land_clearing_contractor",
                "audience_type_names": "Erosion Control Contractor | Land Clearing Contractor",
                "state": "",
                "querystring": ""
            }
        ],
    ),
    db: Session = Depends(get_db),
):
    """
    Bulk upload leads/jobs from JSON body (application/json).

    Accepts:
    - Single object: {...}
    - Array of objects: [{...}, {...}]

    Expected fields:
    - queue_id, rule_id, recipient_group, recipient_group_id
    - day_offset, anchor_event, anchor_at, due_at
    - permit_id, permit_number, permit_status, permit_type_norm
    - job_address, project_description, project_cost_total, project_cost_source
    - source_county, source_system, routing_anchor_at
    - first_seen_at, last_seen_at
    - contractor_name, contractor_company, contractor_email, contractor_phone
    - audience_type_slugs, audience_type_names, state, querystring
    - trs_score (automatically calculated)

    No authentication required.
    """
    try:
        # Body is already parsed by FastAPI
        # Convert to list if single object
        if isinstance(body, dict):
            data = [body]
        elif isinstance(body, list):
            data = body
        else:
            raise HTTPException(status_code=400, detail="Body must be a JSON object or array of objects")
        
        # Validate and convert to LeadUploadItem objects
        leads = []
        for idx, item in enumerate(data):
            try:
                lead = schemas.subscription.LeadUploadItem(**item)
                leads.append(lead)
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid data at index {idx}: {str(e)}"
                )
        
        # Convert to DataFrame
        df = pd.DataFrame([lead.dict() for lead in leads])

        total_rows = len(df)
        successful = 0
        failed = 0
        errors = []
        created_jobs = []  # Collect created job objects

        # Normalize column names
        df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')

        # Process each row (same logic as file upload)
        for index, row in df.iterrows():
            try:
                # Helper to get value
                def get_value(field_name, default=None):
                    if field_name in df.columns and pd.notna(row.get(field_name)):
                        return row.get(field_name)
                    return default

                # Parse datetime fields
                def parse_datetime(value):
                    if not value or pd.isna(value):
                        return None
                    try:
                        parsed = pd.to_datetime(value)
                        if hasattr(parsed, 'to_pydatetime'):
                            return parsed.to_pydatetime()
                        return parsed
                    except Exception as e:
                        logger.warning(f"Failed to parse datetime '{value}': {str(e)}")
                        return None

                trs = calculate_trs_score(
                    project_value=get_value('project_cost_total'),
                    permit_status=get_value('permit_status'),
                    phone_number=get_value('contractor_phone'),
                    email=get_value('contractor_email'),
                    project_description=get_value('project_description'),
                    job_address=get_value('job_address'),
                    has_documents=False  # Bulk uploads don't support documents
                )
                
                anchor_at = parse_datetime(get_value('anchor_at'))
                due_at = parse_datetime(get_value('due_at'))
                day_offset = int(get_value('day_offset', 0))
                
                job_review_status = "pending"
                review_posted_at = None
                now = datetime.utcnow()
                
                # Simplified logic: only "posted" or "pending"
                if anchor_at and due_at:
                    posting_time = anchor_at + timedelta(days=day_offset)
                    
                    # If current time >= posting_time OR due_at has passed → posted
                    if now >= posting_time or now > due_at:
                        job_review_status = "posted"
                        review_posted_at = now
                    # Otherwise → pending (offset days remaining)
                    else:
                        job_review_status = "pending"
                elif due_at:
                    # Has due_at but no anchor_at - check if due_at passed
                    if now > due_at:
                        job_review_status = "posted"
                        review_posted_at = now
                    else:
                        job_review_status = "pending"
                else:
                    # No timing info - default to pending
                    job_review_status = "pending"


                def safe_int(value):
                    if value is None or (isinstance(value, str) and not value.strip()):
                        return None
                    try:
                        return int(value)
                    except (ValueError, TypeError):
                        return None
                
                def safe_str(value):
                    if value is None:
                        return None
                    val_str = str(value).strip()
                    return val_str if val_str else None
                
                permit_type_raw = safe_str(get_value('permit_type_norm'))
                if permit_type_raw:
                    if permit_type_raw.lower().endswith(' permit'):
                        permit_type_raw = permit_type_raw[:-7].strip()
                    elif permit_type_raw.lower().endswith('permit'):
                        permit_type_raw = permit_type_raw[:-6].strip()
                    permit_type_normalized = f"{permit_type_raw} Project"
                else:
                    permit_type_normalized = None
                
                job = models.user.Job(
                    queue_id=safe_int(get_value('queue_id')),
                    rule_id=safe_int(get_value('rule_id')),
                    recipient_group=safe_str(get_value('recipient_group')),
                    recipient_group_id=safe_int(get_value('recipient_group_id')),
                    day_offset=day_offset,
                    anchor_event=safe_str(get_value('anchor_event')),
                    anchor_at=anchor_at,
                    due_at=due_at,
                    permit_id=safe_int(get_value('permit_id')),
                    # Direct mapping from input fields
                    permit_number=safe_str(get_value('project_number')),  # From project_number
                    permit_status=safe_str(get_value('permit_project_status')),  # From permit_project_status
                    permit_type_norm=permit_type_normalized,
                    job_address=safe_str(get_value('project_address')),  # From project_address
                    project_description=safe_str(get_value('project_description')),
                    project_cost_total=safe_int(get_value('project_cost')),  # From project_cost,
                    project_cost_source=safe_str(get_value('project_cost_source')),
                    source_county=safe_str(get_value('source_county')),
                    source_system=safe_str(get_value('source_system')),
                    routing_anchor_at=parse_datetime(get_value('routing_anchor_at')),
                    first_seen_at=parse_datetime(get_value('first_seen_at')),
                    last_seen_at=parse_datetime(get_value('last_seen_at')),
                    contractor_name=safe_str(get_value('contractor_name')),
                    contractor_company=safe_str(get_value('contractor_company')),
                    contractor_email=safe_str(get_value('contractor_email')),
                    contractor_phone=safe_str(get_value('contractor_phone')),
                    audience_type_slugs=safe_str(get_value('audience_type_slugs')),
                    audience_type_names=safe_str(get_value('audience_type_names')),
                    state=safe_str(get_value('state')),
                    querystring=safe_str(get_value('querystring')),
                    trs_score=trs,
                    uploaded_by_contractor=False,
                    uploaded_by_user_id=None,
                    job_review_status=job_review_status,
                    review_posted_at=review_posted_at,
                    # New fields for enhanced project data
                    project_number=safe_str(get_value('project_number')),
                    project_type=safe_str(get_value('project_type')),
                    project_sub_type=safe_str(get_value('project_sub_type')),
                    project_status=safe_str(get_value('permit_project_status')),  # Maps from permit_project_status
                    project_cost=safe_int(get_value('project_cost')),
                    project_address=safe_str(get_value('project_address')),
                    owner_name=safe_str(get_value('owner_name')),
                    applicant_name=safe_str(get_value('applicant_name')),
                    applicant_email=safe_str(get_value('applicant_email')),
                    applicant_phone=safe_str(get_value('applicant_phone')),
                    contractor_company_and_address=safe_str(get_value('contractor_company_and_address')),
                    permit_raw=safe_str(get_value('permit_raw')),
                )

                db.add(job)
                created_jobs.append(job)  # Collect job for ID retrieval
                successful += 1

            except Exception as e:
                failed += 1
                errors.append(f"Row {index + 1}: {str(e)}")
                logger.error(f"Error processing row {index + 1}: {str(e)}")

        db.commit()
        
        # Refresh all jobs to get their auto-generated IDs
        for job in created_jobs:
            db.refresh(job)

        logger.info(
            f"JSON bulk upload completed: {successful} successful, {failed} failed out of {total_rows} total"
        )

        return {
            "total_rows": total_rows,
            "successful": successful,
            "failed": failed,
            "errors": errors[:50],
            "job_ids": [job.id for job in created_jobs],  # Return IDs of created jobs
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error during JSON bulk upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process JSON: {str(e)}")


@router.get("/job/{job_id}")
def get_job_by_id(
    job_id: int,
    db: Session = Depends(get_db),
):
    """
    Get complete job/lead details by job ID.
    
    Public endpoint - No authentication required.
    Returns all job data from the database.
    
    Path parameters:
    - job_id: ID of the job to retrieve
    
    Returns:
    - Complete job object with all fields
    """
    # Query job by ID
    job = db.query(models.user.Job).filter(models.user.Job.id == job_id).first()
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job with ID {job_id} not found"
        )
    
    # Return all job data as dictionary
    return {
        "id": job.id,
        "queue_id": job.queue_id,
        "rule_id": job.rule_id,
        "recipient_group": job.recipient_group,
        "recipient_group_id": job.recipient_group_id,
        "day_offset": job.day_offset,
        "anchor_event": job.anchor_event,
        "anchor_at": job.anchor_at,
        "due_at": job.due_at,
        "permit_id": job.permit_id,
        "permit_number": job.permit_number,
        "permit_status": job.permit_status,
        "permit_type": job.permit_type,
        "permit_type_norm": job.audience_type_names,  # Use audience_type_names for human-readable format
        "job_address": job.job_address,
        "project_description": job.project_description,
        "project_cost_total": job.project_cost_total,
        "project_cost_source": job.project_cost_source,
        "source_county": job.source_county,
        "source_system": job.source_system,
        "routing_anchor_at": job.routing_anchor_at,
        "first_seen_at": job.first_seen_at,
        "last_seen_at": job.last_seen_at,
        "contractor_name": job.contractor_name,
        "contractor_company": job.contractor_company,
        "contractor_email": job.contractor_email,
        "contractor_phone": job.contractor_phone,
        "email": job.email,
        "phone_number": job.phone_number,
        "audience_type_slugs": job.audience_type_slugs,
        "audience_type_names": job.audience_type_names,
        "state": job.state,
        "country_city": job.country_city,
        "querystring": job.querystring,
        "trs_score": job.trs_score,
        "uploaded_by_contractor": job.uploaded_by_contractor,
        "uploaded_by_user_id": job.uploaded_by_user_id,
        "job_review_status": job.job_review_status,
        "review_posted_at": job.review_posted_at,
        "job_cost": job.job_cost,
        "property_type": job.property_type,
        "job_documents": job.job_documents,
        "job_group_id": job.job_group_id,
        "project_number": job.project_number,
        "project_type": job.project_type,
        "project_sub_type": job.project_sub_type,
        "project_status": job.project_status,
        "project_cost": job.project_cost,
        "project_address": job.project_address,
        "owner_name": job.owner_name,
        "applicant_name": job.applicant_name,
        "applicant_email": job.applicant_email,
        "applicant_phone": job.applicant_phone,
        "contractor_company_and_address": job.contractor_company_and_address,
        "permit_raw": job.permit_raw,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


@router.post("/unlock/{job_id}", response_model=schemas.subscription.JobDetailResponse)
def unlock_job(
    job_id: int,
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """Unlock a job/lead by spending credits."""
    # Check if job exists and is posted
    job = db.query(models.user.Job).filter(
        models.user.Job.id == job_id,
        models.user.Job.job_review_status == 'posted'
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check if already unlocked
    already_unlocked = (
        db.query(models.user.UnlockedLead)
        .filter(
            and_(
                models.user.UnlockedLead.user_id == effective_user.id,
                models.user.UnlockedLead.job_id == job_id,
            )
        )
        .first()
    )

    if already_unlocked:
        # Return full job details if already unlocked
        return job

    # Get credit cost from TRS score (default to 1 if not set)
    credit_cost = job.trs_score if job.trs_score else 1

    # Get subscriber info
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.user_id == effective_user.id)
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
        user_id=effective_user.id, job_id=job_id, credits_spent=credit_cost
    )

    db.add(unlocked_lead)
    db.commit()
    db.refresh(subscriber)

    logger.info(
        f"User {effective_user.email} unlocked job {job_id} for {credit_cost} credits"
    )

    # Send celebration email to user
    try:
        import asyncio
        from src.app.utils.email import send_lead_unlock_email
        
        # Get user name (prefer company name, fallback to email)
        user_name = getattr(effective_user, 'company_name', None) or effective_user.email
        
        # Get job location
        job_location = f"{job.city}, {job.state}" if job.city and job.state else (job.state or "N/A")
        
        # Send email asynchronously
        asyncio.create_task(send_lead_unlock_email(
            recipient_email=effective_user.email,
            user_name=user_name,
            job_title=job.job_title or "New Lead",
            job_location=job_location,
            credits_spent=credit_cost
        ))
        logger.info(f"Lead unlock email queued for {effective_user.email}")
    except Exception as email_error:
        # Don't fail the unlock if email fails
        logger.error(f"Failed to send lead unlock email to {effective_user.email}: {email_error}")

    return job


@router.get("/feed")
def get_job_feed(
    state: Optional[str] = Query(None, description="Comma-separated list of states (overrides profile)"),
    country_city: Optional[str] = Query(None, description="Comma-separated list of cities/counties (overrides profile)"),
    user_type: Optional[str] = Query(None, description="Comma-separated list of user types (overrides profile)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Get job feed with hybrid filtering.

    Accepts state, country_city, and user_type as optional query parameters.
    If not provided, uses values from user profile (Contractor or Supplier table).
    
    Query Parameters (all optional, override profile values):
    - state: Comma-separated states (e.g., "NC,FL")
    - country_city: Comma-separated cities/counties (e.g., "Mecklenburg County,Miami-Dade County")
    - user_type: Comma-separated user types (e.g., "erosion_control_contractor,electrical_contractor")

    Returns paginated job results (only posted jobs).
    """
    # Check user role
    if effective_user.role not in ["Contractor", "Supplier"]:
        raise HTTPException(
            status_code=403, detail="User must be a Contractor or Supplier"
        )

    # Get user profile for state/country
    user_profile = None
    if effective_user.role == "Contractor":
        user_profile = (
            db.query(models.user.Contractor)
            .filter(models.user.Contractor.user_id == effective_user.id)
            .first()
        )
    else:  # Supplier
        user_profile = (
            db.query(models.user.Supplier)
            .filter(models.user.Supplier.user_id == effective_user.id)
            .first()
        )

    if not user_profile:
        raise HTTPException(
            status_code=403,
            detail="Please complete your profile to access job feed",
        )

    # Parse query parameters or use profile values (hybrid override)
    # User Type
    if user_type:
        user_type_list = [ut.strip() for ut in user_type.split(",") if ut.strip()]
    else:
        user_type_list = []

    # State
    if state:
        state_list = [s.strip() for s in state.split(",") if s.strip()]
    else:
        # Use profile values
        if effective_user.role == "Contractor":
            state_list = user_profile.state if user_profile.state else []
        else:  # Supplier
            state_list = user_profile.service_states if user_profile.service_states else []
    
    # Country/City
    if country_city:
        country_city_list = [c.strip() for c in country_city.split(",") if c.strip()]
    else:
        # Use profile values
        country_city_list = user_profile.country_city if user_profile.country_city else []


    # Get list of not-interested job IDs for this user
    not_interested_job_ids = (
        db.query(models.user.NotInterestedJob.job_id)
        .filter(models.user.NotInterestedJob.user_id == effective_user.id)
        .all()
    )
    not_interested_ids = [job_id[0] for job_id in not_interested_job_ids]

    # Get list of unlocked job IDs for this user
    unlocked_job_ids = (
        db.query(models.user.UnlockedLead.job_id)
        .filter(models.user.UnlockedLead.user_id == effective_user.id)
        .all()
    )
    unlocked_ids = [job_id[0] for job_id in unlocked_job_ids]

    # Get saved job ids
    saved_job_ids = (
        db.query(models.user.SavedJob.job_id)
        .filter(models.user.SavedJob.user_id == effective_user.id)
        .all()
    )
    saved_ids = {job_id[0] for job_id in saved_job_ids}

    # Combine excluded IDs (not-interested, unlocked, saved)
    excluded_ids = list(set(not_interested_ids + unlocked_ids + list(saved_ids)))

    # Build search conditions based on user_type parameter
    search_conditions = []

    # Match if ANY user_type in user_type_list matches ANY value in audience_type_slugs
    if user_type_list:
        audience_conditions = []
        for ut in user_type_list:
            audience_conditions.append(
                models.user.Job.audience_type_slugs.ilike(f"%{ut}%")
            )
        if audience_conditions:
            search_conditions.append(or_(*audience_conditions))

    # Build base query - only posted jobs
    base_query = db.query(models.user.Job).filter(
        models.user.Job.job_review_status == "posted"
    )


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
            models.user.Job.source_county.ilike(f"%{city}%")
            for city in country_city_list
        ]
        base_query = base_query.filter(or_(*city_conditions))

    # Get total count
    total_count = base_query.count()

    # Get all results ordered by TRS score for deduplication
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
    
    logger.info(f"/feed: {len(all_jobs)} jobs → {len(deduplicated_jobs)} unique ({len(all_jobs) - len(deduplicated_jobs)} duplicates removed)")
    
    # Apply pagination to deduplicated results
    offset = (page - 1) * page_size
    paginated_jobs = deduplicated_jobs[offset:offset + page_size]

    # Convert to simplified response format
    job_responses = [
        {
            "id": job.id,
            "trs_score": job.trs_score,
            "permit_type": job.permit_type,
            "country_city": job.country_city,
            "state": job.state,
            "project_description": job.project_description,
            "project_cost_total": job.project_cost_total,
            "property_type": job.property_type,
            "job_review_status": job.job_review_status,
            "review_posted_at": job.review_posted_at,
            "saved": job.id in saved_ids,
        }
        for job in paginated_jobs
    ]

    return {
        "jobs": job_responses,
        "total": len(deduplicated_jobs),
        "page": page,
        "page_size": page_size,
        "total_pages": (len(deduplicated_jobs) + page_size - 1) // page_size,
    }


@router.get("/all-my-saved-jobs")
def get_all_my_saved_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Get all saved jobs for the current user without any filters.

    Returns paginated list of all jobs that user has saved/bookmarked.
    No filtering by states, countries, or categories.
    """
    # Get list of saved job IDs for this user
    saved_job_ids = (
        db.query(models.user.SavedJob.job_id)
        .filter(models.user.SavedJob.user_id == effective_user.id)
        .all()
    )
    saved_ids = [job_id[0] for job_id in saved_job_ids]

    # If no saved jobs, return empty result
    if not saved_ids:
        return {
            "jobs": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
        }

    # Build query - only saved jobs that are posted
    base_query = db.query(models.user.Job).filter(
        models.user.Job.id.in_(saved_ids),
        models.user.Job.job_review_status == 'posted'
    )

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

    # Convert to response format
    job_responses = [
        {
            "id": job.id,
            "trs_score": job.trs_score,
            "permit_type": job.permit_type,
            "country_city": job.country_city,
            "state": job.state,
            "project_description": job.project_description,
            "project_cost_total": job.project_cost_total,
            "property_type": job.property_type,
            "job_review_status": job.job_review_status,
            "review_posted_at": job.review_posted_at,
            "saved": job.id in saved_ids,
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


@router.get("/my-saved-job-feed")
def get_my_saved_job_feed(
    state: Optional[str] = Query(None, description="Comma-separated list of states"),
    country_city: Optional[str] = Query(None, description="Comma-separated list of cities/counties"),
    user_type: Optional[str] = Query(None, description="Comma-separated list of user types"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Get saved jobs feed with hybrid filtering.

    Returns only jobs that user has saved.
    Accepts state, country_city, and user_type as optional query parameters.
    If not provided, uses values from user profile (Contractor or Supplier table).

    Query Parameters:
    - state: Optional comma-separated states (overrides profile)
    - country_city: Optional comma-separated cities/counties (overrides profile)
    - user_type: Optional comma-separated user types (overrides profile)

    Returns paginated job results from user's saved jobs.
    """
    # Check user role
    if effective_user.role not in ["Contractor", "Supplier"]:
        raise HTTPException(
            status_code=403, detail="User must be a Contractor or Supplier"
        )

    # Get user profile for fallback values
    user_profile = None
    if effective_user.role == "Contractor":
        user_profile = (
            db.query(models.user.Contractor)
            .filter(models.user.Contractor.user_id == effective_user.id)
            .first()
        )
    else:  # Supplier
        user_profile = (
            db.query(models.user.Supplier)
            .filter(models.user.Supplier.user_id == effective_user.id)
            .first()
        )

    if not user_profile:
        raise HTTPException(
            status_code=403,
            detail="Please complete your profile to access saved job feed",
        )

    # Parse query parameters or use profile values
    # State
    if state:
        state_list = [s.strip() for s in state.split(",") if s.strip()]
    else:
        # Use profile values
        if effective_user.role == "Contractor":
            state_list = user_profile.state if user_profile.state else []
        else:  # Supplier
            state_list = user_profile.service_states if user_profile.service_states else []
    
    # Country/City
    if country_city:
        country_city_list = [c.strip() for c in country_city.split(",") if c.strip()]
    else:
        # Use profile values
        country_city_list = user_profile.country_city if user_profile.country_city else []
    
    # User Type
    user_type_list = []
    if user_type:
        user_type_list = [ut.strip() for ut in user_type.split(",") if ut.strip()]

    # Get list of saved job IDs for this user
    saved_job_ids = (
        db.query(models.user.SavedJob.job_id)
        .filter(models.user.SavedJob.user_id == effective_user.id)
        .all()
    )
    saved_ids = [job_id[0] for job_id in saved_job_ids]

    # Build base query - only saved jobs that are posted
    base_query = db.query(models.user.Job).filter(
        models.user.Job.id.in_(saved_ids),
        models.user.Job.job_review_status == 'posted'
    )

    # If no saved jobs, return empty result
    if not saved_ids:
        return {
            "jobs": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
        }

    # Build search conditions based on user_type
    search_conditions = []

    # Match if ANY user_type in user_type_list matches ANY value in audience_type_slugs
    if user_type_list:
        audience_conditions = []
        for ut in user_type_list:
            audience_conditions.append(
                models.user.Job.audience_type_slugs.ilike(f"%{ut}%")
            )
        if audience_conditions:
            search_conditions.append(or_(*audience_conditions))

    # Apply user_type search conditions
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
            models.user.Job.source_county.ilike(f"%{city}%")
            for city in country_city_list
        ]
        base_query = base_query.filter(or_(*city_conditions))

    # Get all results for deduplication
    all_jobs = base_query.order_by(
        models.user.Job.trs_score.desc(), models.user.Job.created_at.desc()
    ).all()
    
    # Deduplicate jobs
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
    
    logger.info(f"/my-saved-job-feed: {len(all_jobs)} jobs → {len(deduplicated_jobs)} unique ({len(all_jobs) - len(deduplicated_jobs)} duplicates removed)")
    
    # Apply pagination to deduplicated results
    offset = (page - 1) * page_size
    paginated_jobs = deduplicated_jobs[offset:offset + page_size]

    # Convert to response format
    job_responses = [
        {
            "id": job.id,
            "trs_score": job.trs_score,
            "permit_type": job.permit_type,
            "country_city": job.country_city,
            "state": job.state,
            "project_description": job.project_description,
            "property_type": job.property_type,
            "job_review_status": job.job_review_status,
            "review_posted_at": job.review_posted_at,
            "saved": job.id in saved_ids,
        }
        for job in paginated_jobs
    ]

    return {
        "jobs": job_responses,
        "total": len(deduplicated_jobs),
        "page": page,
        "page_size": page_size,
        "total_pages": (len(deduplicated_jobs) + page_size - 1) // page_size,
    }


@router.get("/all-my-jobs-desktop")
def get_all_my_jobs_desktop(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Get all unlocked jobs for desktop view with detailed information.

    Returns paginated list of all jobs that user has unlocked/purchased
    with extended fields including contact information.
    """
    # Get list of unlocked job IDs for this user
    unlocked_job_ids = (
        db.query(models.user.UnlockedLead.job_id)
        .filter(models.user.UnlockedLead.user_id == effective_user.id)
        .all()
    )
    unlocked_ids = [job_id[0] for job_id in unlocked_job_ids]

    # Get list of saved job IDs for this user so we can mark saved state
    saved_job_ids = (
        db.query(models.user.SavedJob.job_id)
        .filter(models.user.SavedJob.user_id == effective_user.id)
        .all()
    )
    saved_ids = {job_id[0] for job_id in saved_job_ids}

    # If no unlocked jobs, return empty result
    if not unlocked_ids:
        return {
            "jobs": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
        }

    # Build query - only unlocked jobs that are posted
    base_query = db.query(models.user.Job).filter(
        models.user.Job.id.in_(unlocked_ids),
        models.user.Job.job_review_status == 'posted'
    )

    # Get all results for deduplication
    all_jobs = base_query.order_by(models.user.Job.review_posted_at.desc()).all()
    
    # Deduplicate jobs
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
    
    logger.info(f"/all-my-jobs-desktop: {len(all_jobs)} jobs → {len(deduplicated_jobs)} unique ({len(all_jobs) - len(deduplicated_jobs)} duplicates removed)")
    
    # Apply pagination to deduplicated results
    offset = (page - 1) * page_size
    paginated_jobs = deduplicated_jobs[offset:offset + page_size]

    # Convert to response format with extended fields
    job_responses = [
        {
            "id": job.id,
            "permit_type": job.permit_type,
            "job_cost": job.job_cost,
            "job_address": job.job_address,
            "trs_score": job.trs_score,
            "email": job.email,
            "phone_number": job.phone_number,
            "country_city": job.country_city,
            "state": job.state,
            "project_description": job.project_description,
            "property_type": job.property_type,
            "job_review_status": job.job_review_status,
            "review_posted_at": job.review_posted_at,
            "saved": job.id in saved_ids,
        }
        for job in paginated_jobs
    ]

    return {
        "jobs": job_responses,
        "total": len(deduplicated_jobs),
        "page": page,
        "page_size": page_size,
        "total_pages": (len(deduplicated_jobs) + page_size - 1) // page_size,
    }


@router.get("/all-my-jobs-desktop-search")
def get_all_my_jobs_desktop_search(
    keyword: str = Query(..., description="Search keyword to filter jobs"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Search unlocked jobs for desktop view with keyword filtering.

    Returns paginated list of unlocked jobs matching the search keyword
    with extended fields including contact information.
    Searches across multiple fields: permit_type, project_description, job_address,
    country_city, state, email, and phone_number.
    """
    # Get list of unlocked job IDs for this user
    unlocked_job_ids = (
        db.query(models.user.UnlockedLead.job_id)
        .filter(models.user.UnlockedLead.user_id == effective_user.id)
        .all()
    )
    unlocked_ids = [job_id[0] for job_id in unlocked_job_ids]

    # If no unlocked jobs, return empty result
    if not unlocked_ids:
        return {
            "jobs": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
        }

    # Build base query - only unlocked jobs
    base_query = db.query(models.user.Job).filter(models.user.Job.id.in_(unlocked_ids))

    # Also get saved job ids so we can mark saved state when rendering jobs
    saved_job_ids = (
        db.query(models.user.SavedJob.job_id)
        .filter(models.user.SavedJob.user_id == effective_user.id)
        .all()
    )
    saved_ids = {job_id[0] for job_id in saved_job_ids}

    # Apply keyword search across multiple fields
    keyword_pattern = f"%{keyword}%"
    search_conditions = [
        models.user.Job.permit_type_norm.ilike(keyword_pattern),
        models.user.Job.project_description.ilike(keyword_pattern),
        models.user.Job.job_address.ilike(keyword_pattern),
        models.user.Job.source_county.ilike(keyword_pattern),
        models.user.Job.state.ilike(keyword_pattern),
        models.user.Job.contractor_email.ilike(keyword_pattern),
        models.user.Job.contractor_phone.ilike(keyword_pattern),
    ]
    base_query = base_query.filter(or_(*search_conditions))

    # Get all results for deduplication
    all_jobs = base_query.order_by(models.user.Job.review_posted_at.desc()).all()
    
    # Deduplicate jobs
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
    
    logger.info(f"/all-my-jobs-desktop-search: {len(all_jobs)} jobs → {len(deduplicated_jobs)} unique ({len(all_jobs) - len(deduplicated_jobs)} duplicates removed)")
    
    # Apply pagination to deduplicated results
    offset = (page - 1) * page_size
    paginated_jobs = deduplicated_jobs[offset:offset + page_size]

    # Convert to response format with extended fields
    job_responses = [
        {
            "id": job.id,
            "permit_type": job.permit_type,
            "job_cost": job.job_cost,
            "job_address": job.job_address,
            "trs_score": job.trs_score,
            "email": job.email,
            "phone_number": job.phone_number,
            "country_city": job.country_city,
            "state": job.state,
            "project_description": job.project_description,
            "project_cost_total": job.project_cost_total,
            "property_type": job.property_type,
            "job_review_status": job.job_review_status,
            "review_posted_at": job.review_posted_at,
            "saved": job.id in saved_ids,
        }
        for job in paginated_jobs
    ]

    return {
        "jobs": job_responses,
        "total": len(deduplicated_jobs),
        "page": page,
        "page_size": page_size,
        "total_pages": (len(deduplicated_jobs) + page_size - 1) // page_size,
    }


@router.get("/all-my-jobs")
def get_all_my_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Get all unlocked jobs for the current user with pagination.

    Returns all jobs that the user has purchased (unlocked), without any filters.
    Ordered by TRS score (highest quality first) and creation date.

    Returns complete job details including contact information since user owns these leads.
    """
    # Get list of unlocked job IDs for this user
    unlocked_job_ids = (
        db.query(models.user.UnlockedLead.job_id)
        .filter(models.user.UnlockedLead.user_id == effective_user.id)
        .all()
    )
    unlocked_ids = [job_id[0] for job_id in unlocked_job_ids]

    # Get list of saved job IDs for this user so we can mark saved state
    saved_job_ids = (
        db.query(models.user.SavedJob.job_id)
        .filter(models.user.SavedJob.user_id == effective_user.id)
        .all()
    )
    saved_ids = {job_id[0] for job_id in saved_job_ids}

    # If no unlocked jobs, return empty result
    if not unlocked_ids:
        return {
            "jobs": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
        }

    # Build base query - only unlocked jobs that are posted
    base_query = db.query(models.user.Job).filter(
        models.user.Job.id.in_(unlocked_ids),
        models.user.Job.job_review_status == 'posted'
    )

    # Get all results for deduplication
    all_jobs = base_query.order_by(models.user.Job.review_posted_at.desc()).all()
    
    # Deduplicate jobs
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
    
    logger.info(f"/all-my-jobs: {len(all_jobs)} jobs → {len(deduplicated_jobs)} unique ({len(all_jobs) - len(deduplicated_jobs)} duplicates removed)")
    
    # Apply pagination to deduplicated results
    offset = (page - 1) * page_size
    paginated_jobs = deduplicated_jobs[offset:offset + page_size]

    # Convert to response format with all job details
    job_responses = [
        {
            "id": job.id,
            "trs_score": job.trs_score,
            "permit_type": job.permit_type,
            "country_city": job.country_city,
            "state": job.state,
            "project_description": job.project_description,
            "project_cost_total": job.project_cost_total,
            "property_type": job.property_type,
            "job_review_status": job.job_review_status,
            "job_cost": job.job_cost,
            "job_address": job.job_address,
            "review_posted_at": job.review_posted_at,
            "saved": job.id in saved_ids,
        }
        for job in paginated_jobs
    ]

    return {
        "jobs": job_responses,
        "total": len(deduplicated_jobs),
        "page": page,
        "page_size": page_size,
        "total_pages": (len(deduplicated_jobs) + page_size - 1) // page_size,
    }


@router.get("/view-details/{job_id}")
def view_job_details(
    job_id: int,
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    View complete details of an unlocked job including user's notes.

    Returns all job information (same as export) plus editable notes field.
    User must have unlocked this job to view details.
    """
    # Check if user has unlocked this job
    unlocked_lead = (
        db.query(models.user.UnlockedLead)
        .filter(
            models.user.UnlockedLead.user_id == effective_user.id,
            models.user.UnlockedLead.job_id == job_id,
        )
        .first()
    )

    if not unlocked_lead:
        raise HTTPException(
            status_code=403,
            detail="You have not unlocked this job. Please unlock it first to view details.",
        )

    # Get the job details - only posted jobs
    job = db.query(models.user.Job).filter(
        models.user.Job.id == job_id,
        models.user.Job.job_review_status == 'posted'
    ).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Return complete job details with notes
    return {
        "id": job.id,
        "permit_number": job.permit_number,
        "permit_type": job.permit_type,
        "permit_type_norm": job.audience_type_names,  # Use audience_type_names for human-readable format
        "permit_status": job.permit_status,
        "job_cost": job.job_cost,
        "job_address": job.job_address,
        "country_city": job.country_city,
        "state": job.state,
        "project_description": job.project_description,
        "project_cost_total": job.project_cost_total,
        "property_type": job.property_type,
        "job_review_status": job.job_review_status,
        "email": job.email,
        "phone_number": job.phone_number,
        # Contact information
        "contractor_email": job.contractor_email,
        "contractor_phone": job.contractor_phone,
        "applicant_email": job.applicant_email,
        "applicant_phone": job.applicant_phone,
        "trs_score": job.trs_score,
        "review_posted_at": job.review_posted_at,
        "notes": unlocked_lead.notes,
        "unlocked_at": (
            unlocked_lead.unlocked_at.isoformat() if unlocked_lead.unlocked_at else None
        ),
    }


@router.put("/update-notes/{job_id}")
def update_job_notes(
    job_id: int,
    notes: str = None,
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Update notes for an unlocked job.

    Allows user to add or edit their personal notes about a specific unlocked job.
    Notes are stored in the unlocked_leads table.
    """
    # Check if user has unlocked this job
    unlocked_lead = (
        db.query(models.user.UnlockedLead)
        .filter(
            models.user.UnlockedLead.user_id == effective_user.id,
            models.user.UnlockedLead.job_id == job_id,
        )
        .first()
    )

    if not unlocked_lead:
        raise HTTPException(
            status_code=403,
            detail="You have not unlocked this job. Cannot update notes for jobs you don't own.",
        )

    # Update notes
    unlocked_lead.notes = notes
    db.commit()
    db.refresh(unlocked_lead)

    return {
        "message": "Notes updated successfully",
        "job_id": job_id,
        "notes": unlocked_lead.notes,
    }


@router.post("/my-feed-not-interested/{job_id}")
def mark_my_feed_not_interested(
    job_id: int,
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Mark a job from my feed as not interested.

    Adds the job to user's not-interested list so it won't appear in future feeds.
    If the job was saved, removes it from saved jobs first.
    Can be used for jobs in /jobs/feed, /jobs/my-job-feed, /jobs/all, etc.
    """
    # Verify the job exists and is posted
    job = db.query(models.user.Job).filter(
        models.user.Job.id == job_id,
        models.user.Job.job_review_status == 'posted'
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check if already marked as not interested
    existing = (
        db.query(models.user.NotInterestedJob)
        .filter(
            models.user.NotInterestedJob.user_id == effective_user.id,
            models.user.NotInterestedJob.job_id == job_id,
        )
        .first()
    )

    if existing:
        return {
            "message": "Job already marked as not interested",
            "job_id": job_id,
        }

    # Remove from saved jobs if it exists
    saved_job = (
        db.query(models.user.SavedJob)
        .filter(
            models.user.SavedJob.user_id == effective_user.id,
            models.user.SavedJob.job_id == job_id,
        )
        .first()
    )
    
    if saved_job:
        db.delete(saved_job)

    # Create new not-interested entry
    not_interested = models.user.NotInterestedJob(
        user_id=effective_user.id,
        job_id=job_id,
    )

    db.add(not_interested)
    db.commit()

    return {
        "message": "Job marked as not interested successfully",
        "job_id": job_id,
    }


@router.post("/upload-temp-documents")
def upload_temp_documents(
    files: List[UploadFile] = File(...),
    temp_upload_id: str = Form(None),  # Optional: reuse existing upload session
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Upload documents temporarily for preview before job submission.
    
    Parameters:
    - files: Files to upload
    - temp_upload_id: (Optional) Existing temp_upload_id to add more documents to
    
    Returns temp_upload_id and document previews.
    Documents expire after 1 hour if not linked to a job.
    """
    import uuid
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    
    # Process uploaded files
    documents = []
    allowed_types = ["application/pdf", "image/jpeg", "image/jpg", "image/png"]
    max_file_size = 10 * 1024 * 1024  # 10MB per file
    
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="At least one file is required")
    
    for file in files:
        # Validate file type
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"File type {file.content_type} not allowed. Only PDF, JPG, PNG are supported."
            )
        
        # Read file content
        file_content = file.file.read()
        
        # Validate file size
        if len(file_content) > max_file_size:
            raise HTTPException(
                status_code=400,
                detail=f"File {file.filename} exceeds 10MB limit"
            )
        
        # Convert to base64
        file_base64 = base64.b64encode(file_content).decode('utf-8')
        
        # Generate unique document ID
        doc_id = f"DOC-{uuid.uuid4().hex[:12].upper()}"
        
        # Store document metadata
        documents.append({
            "document_id": doc_id,
            "filename": file.filename,
            "content_type": file.content_type,
            "size": len(file_content),
            "data": file_base64
        })
    
    # Check if reusing existing upload session
    if temp_upload_id:
        logger.info(f"Reusing existing upload session: {temp_upload_id}")
        # Find existing temp document
        temp_doc = (
            db.query(models.user.TempDocument)
            .filter(
                models.user.TempDocument.temp_upload_id == temp_upload_id,
                models.user.TempDocument.user_id == effective_user.id
            )
            .first()
        )
        
        if not temp_doc:
            raise HTTPException(
                status_code=404, 
                detail=f"temp_upload_id {temp_upload_id} not found or does not belong to user"
            )
        
        # Check if expired (only for unlinked documents)
        est_tz = ZoneInfo("America/New_York")
        now_est = datetime.now(est_tz).replace(tzinfo=None)
        
        if not temp_doc.linked_to_job and now_est > temp_doc.expires_at:
            raise HTTPException(
                status_code=400,
                detail=f"Upload session {temp_upload_id} has expired"
            )
        
        # Append new documents to existing ones
        existing_documents = temp_doc.documents or []
        existing_documents.extend(documents)
        temp_doc.documents = existing_documents
        
        # Flag the JSON column as modified (important for SQLAlchemy to detect change)
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(temp_doc, "documents")
        
        # Extend expiration time only if not linked to job
        if not temp_doc.linked_to_job:
            temp_doc.expires_at = now_est + timedelta(hours=1)
            logger.info(f"Extended expiration to {temp_doc.expires_at}")
        else:
            logger.info(f"Documents linked to job - expiration not extended")
        
        db.commit()
        db.refresh(temp_doc)
        
        logger.info(f"Added {len(documents)} documents to {temp_upload_id}. Total: {len(existing_documents)}")
        
    else:
        # Create new upload session
        logger.info("Creating new upload session")
        # Generate unique temp_upload_id
        temp_upload_id = f"TEMP-{uuid.uuid4().hex[:16].upper()}"
        
        # Get current time in EST
        est_tz = ZoneInfo("America/New_York")
        now_est = datetime.now(est_tz).replace(tzinfo=None)
        expires_at = now_est + timedelta(hours=1)
        
        # Save to temp_documents table
        temp_doc = models.user.TempDocument(
            temp_upload_id=temp_upload_id,
            user_id=effective_user.id,
            documents=documents,
            linked_to_job=False,
            expires_at=expires_at
        )
        
        db.add(temp_doc)
        db.commit()
        db.refresh(temp_doc)
        
        logger.info(f"Created new upload session: {temp_upload_id} with {len(documents)} documents")
    
    # Return only metadata without base64 data
    all_documents = temp_doc.documents or []
    documents_metadata = [
        {
            "document_id": doc["document_id"],
            "filename": doc["filename"],
            "content_type": doc["content_type"],
            "size": doc["size"]
        }
        for doc in all_documents
    ]
    
    return {
        "temp_upload_id": temp_upload_id,
        "total_documents": len(all_documents),
        "expires_at": temp_doc.expires_at.isoformat(),
        "documents": documents_metadata
    }


@router.get("/temp-documents/preview")
def get_temp_document_preview(
    document_ids: str = Query(..., description="Comma-separated document IDs"),
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Get preview of specific documents by document IDs with PNG thumbnails.
    Returns thumbnails in format: {document_id, thumbnail, filename, pageCount, fileSize}
    
    Parameters:
    - document_ids: Comma-separated document IDs (e.g., "DOC-ABC123,DOC-DEF456")
    """
    # Parse document IDs
    doc_id_list = [doc_id.strip() for doc_id in document_ids.split(',')]
    from io import BytesIO
    from PIL import Image
    import io
    from datetime import datetime
    from zoneinfo import ZoneInfo
    
    # Get all temp documents for this user
    temp_docs = (
        db.query(models.user.TempDocument)
        .filter(models.user.TempDocument.user_id == effective_user.id)
        .all()
    )
    
    logger.info(f"Found {len(temp_docs)} TempDocument records for user {effective_user.id}")
    
    # Check expiration time
    est_tz = ZoneInfo("America/New_York")
    now_est = datetime.now(est_tz).replace(tzinfo=None)
    
    # Find requested documents across all temp uploads
    found_docs = []
    for idx, temp_doc in enumerate(temp_docs, 1):
        # Allow access if: not expired OR linked to draft/job
        is_accessible = (now_est <= temp_doc.expires_at) or temp_doc.linked_to_job or temp_doc.linked_to_draft
        
        if is_accessible:
            logger.info(f"TempDocument {idx}/{len(temp_docs)} (ID: {temp_doc.id}): Accessible (expired: {now_est > temp_doc.expires_at}, linked_to_job: {temp_doc.linked_to_job}, linked_to_draft: {temp_doc.linked_to_draft}), checking {len(temp_doc.documents)} documents")
            for doc in temp_doc.documents:
                doc_id = doc.get("document_id")
                logger.info(f"  - Checking document: {doc_id} (in request list: {doc_id in doc_id_list})")
                if doc_id in doc_id_list:
                    found_docs.append(doc)
                    logger.info(f"  ✓ Added document {doc_id} to found_docs")
        else:
            logger.info(f"TempDocument {idx}/{len(temp_docs)} (ID: {temp_doc.id}): EXPIRED and not linked (expires_at: {temp_doc.expires_at}, now: {now_est})")
    
    if not found_docs:
        raise HTTPException(status_code=404, detail="No documents found with provided IDs or documents expired")
    
    # Generate thumbnails for found documents
    previews = []
    
    logger.info(f"Found {len(found_docs)} documents to preview for user {effective_user.id}")
    logger.info(f"Document IDs requested: {doc_id_list}")
    
    for idx, doc in enumerate(found_docs, 1):
        doc_id = doc.get("document_id", "unknown")
        filename = doc.get("filename", "unknown")
        content_type = doc.get("content_type", "unknown")
        
        logger.info(f"Processing document {idx}/{len(found_docs)}: {doc_id} - {filename} ({content_type})")
        
        try:
            # Decode base64 data
            logger.debug(f"Decoding base64 data for {doc_id}")
            file_data = base64.b64decode(doc["data"])
            file_size = doc["size"]
            logger.debug(f"Decoded file size: {file_size} bytes")
            
            thumbnail_base64 = None
            page_count = None
            
            # Handle PDFs
            if content_type == "application/pdf":
                logger.info(f"Processing PDF: {filename} (document {idx}/{len(found_docs)})")
                try:
                    import fitz  # PyMuPDF
                    
                    logger.debug(f"Opening PDF document: {filename}")
                    # Open PDF from bytes
                    pdf_document = fitz.open(stream=file_data, filetype="pdf")
                    page_count = len(pdf_document)
                    logger.info(f"PDF {filename} has {page_count} pages")
                    
                    # Get first page
                    logger.debug(f"Rendering first page of {filename}")
                    first_page = pdf_document[0]
                    
                    # Render page to image (matrix for resolution, 2.0 = 144 DPI)
                    mat = fitz.Matrix(2.0, 2.0)
                    pix = first_page.get_pixmap(matrix=mat)
                    logger.debug(f"Pixmap created for {filename}: {pix.width}x{pix.height}")
                    
                    # Convert pixmap to PIL Image
                    img_data = pix.tobytes("png")
                    img = Image.open(BytesIO(img_data))
                    logger.debug(f"PIL Image created for {filename}: {img.size}")
                    
                    # Resize to thumbnail (max 800px width)
                    original_size = img.size
                    img.thumbnail((800, 800), Image.Resampling.LANCZOS)
                    logger.info(f"Thumbnail created for {filename}: {original_size} → {img.size}")
                    
                    # Convert to PNG base64
                    buffer = BytesIO()
                    img.save(buffer, format="PNG")
                    thumbnail_base64 = f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode('utf-8')}"
                    logger.debug(f"Base64 thumbnail generated for {filename}, size: {len(thumbnail_base64)} chars")
                    
                    pdf_document.close()
                    logger.info(f"Successfully generated thumbnail for PDF: {filename}")
                    
                except Exception as e:
                    logger.error(f"Error processing PDF {filename} (document {idx}/{len(found_docs)}): {str(e)}", exc_info=True)
                    logger.warning(f"Falling back to full PDF data for {filename}")
                    # Fallback: return full PDF data
                    thumbnail_base64 = f"data:application/pdf;base64,{doc['data']}"
                    page_count = None
            
            # Handle images (JPG, PNG)
            elif content_type in ["image/jpeg", "image/jpg", "image/png"]:
                logger.info(f"Processing image: {filename} (document {idx}/{len(found_docs)})")
                try:
                    img = Image.open(BytesIO(file_data))
                    logger.debug(f"Image opened: {filename}, size: {img.size}, mode: {img.mode}")
                    
                    # Resize to thumbnail (max 800px width)
                    original_size = img.size
                    img.thumbnail((800, 800), Image.Resampling.LANCZOS)
                    logger.info(f"Thumbnail created for {filename}: {original_size} → {img.size}")
                    
                    # Convert to PNG base64
                    buffer = BytesIO()
                    img.save(buffer, format="PNG")
                    thumbnail_base64 = f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode('utf-8')}"
                    logger.debug(f"Base64 thumbnail generated for {filename}, size: {len(thumbnail_base64)} chars")
                    logger.info(f"Successfully generated thumbnail for image: {filename}")
                    
                except Exception as e:
                    logger.error(f"Error processing image {filename} (document {idx}/{len(found_docs)}): {str(e)}", exc_info=True)
            
            preview = {
                "document_id": doc.get("document_id"),
                "thumbnail": thumbnail_base64,
                "filename": filename,
                "contentType": content_type,  # Add content type for frontend
                "fileSize": file_size
            }
            
            # Add pageCount only for PDFs if available
            if page_count is not None:
                preview["pageCount"] = page_count
            
            previews.append(preview)
            logger.info(f"Added preview for document {idx}/{len(found_docs)}: {doc_id} - thumbnail {'generated' if thumbnail_base64 else 'NOT generated'}")
            
        except Exception as e:
            logger.error(f"Error generating preview for document {idx}/{len(found_docs)} - {doc.get('filename', 'unknown')} (ID: {doc.get('document_id', 'unknown')}): {str(e)}", exc_info=True)
            # Add error preview - still include the document
            error_preview = {
                "document_id": doc.get("document_id"),
                "thumbnail": None,
                "filename": doc.get("filename", "unknown"),
                "contentType": doc.get("content_type", "application/octet-stream"),
                "fileSize": doc.get("size", 0),
                "error": str(e)
            }
            previews.append(error_preview)
            logger.warning(f"Added error preview for document {idx}/{len(found_docs)}: {doc.get('document_id', 'unknown')}")
    
    logger.info(f"Successfully processed {len(previews)} previews out of {len(found_docs)} documents")
    logger.info(f"Previews with thumbnails: {sum(1 for p in previews if p.get('thumbnail'))}")
    logger.info(f"Previews with errors: {sum(1 for p in previews if p.get('error'))}")
    
    return previews


@router.delete("/temp-documents/{temp_upload_id}/{document_id}")
def delete_temp_document(
    temp_upload_id: str,
    document_id: str,
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Delete a specific document by temp_upload_id and document_id from temp uploads.
    
    Path parameters:
    - temp_upload_id: The temporary upload session ID
    - document_id: The specific document ID to delete
    
    Both parameters are required to ensure correct document deletion,
    since a user could upload the same document multiple times in different sessions.
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo
    
    # Get the specific temp document by temp_upload_id
    temp_doc = (
        db.query(models.user.TempDocument)
        .filter(
            models.user.TempDocument.temp_upload_id == temp_upload_id,
            models.user.TempDocument.user_id == effective_user.id
        )
        .first()
    )
    
    if not temp_doc:
        raise HTTPException(
            status_code=404,
            detail="Temporary upload session not found or does not belong to you"
        )
    
    # Check if expired
    est_tz = ZoneInfo("America/New_York")
    now_est = datetime.now(est_tz).replace(tzinfo=None)
    
    if now_est > temp_doc.expires_at:
        raise HTTPException(
            status_code=410,
            detail="Temporary upload has expired"
        )
    
    # Find and remove the document
    original_count = len(temp_doc.documents)
    temp_doc.documents = [
        doc for doc in temp_doc.documents 
        if doc.get("document_id") != document_id
    ]
    
    if len(temp_doc.documents) >= original_count:
        # Document was not found
        raise HTTPException(
            status_code=404,
            detail=f"Document {document_id} not found in upload session {temp_upload_id}"
        )
    
    # Document was found and removed
    if len(temp_doc.documents) == 0:
        # No documents left, delete the entire temp record
        db.delete(temp_doc)
        db.commit()
        
        return {
            "message": "Document deleted successfully. Upload session removed (no documents remaining).",
            "temp_upload_id": temp_upload_id,
            "document_id": document_id,
            "remaining_documents": 0,
            "session_deleted": True
        }
    else:
        # Update with remaining documents
        db.add(temp_doc)
        db.commit()
        
        return {
            "message": "Document deleted successfully",
            "temp_upload_id": temp_upload_id,
            "document_id": document_id,
            "remaining_documents": len(temp_doc.documents),
            "session_deleted": False
        }


@router.get("/my-job-feed")
def get_my_job_feed(
    state: Optional[str] = Query(None, description="Comma-separated list of states"),
    country_city: Optional[str] = Query(None, description="Comma-separated list of cities/counties"),
    user_type: Optional[str] = Query(None, description="Comma-separated list of user types"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Get unlocked jobs feed with hybrid filtering.

    Returns only jobs that user has already unlocked (paid credits for).
    Accepts state, country_city, and user_type as optional query parameters.
    If not provided, uses values from user profile (Contractor or Supplier table).

    Query Parameters:
    - state: Optional comma-separated states (overrides profile)
    - country_city: Optional comma-separated cities/counties (overrides profile)
    - user_type: Optional comma-separated user types (overrides profile)

    Returns paginated job results from user's unlocked leads.
    """
    # Check user role
    if effective_user.role not in ["Contractor", "Supplier"]:
        raise HTTPException(
            status_code=403, detail="User must be a Contractor or Supplier"
        )

    # Get user profile for fallback values
    user_profile = None
    if effective_user.role == "Contractor":
        user_profile = (
            db.query(models.user.Contractor)
            .filter(models.user.Contractor.user_id == effective_user.id)
            .first()
        )
    else:  # Supplier
        user_profile = (
            db.query(models.user.Supplier)
            .filter(models.user.Supplier.user_id == effective_user.id)
            .first()
        )

    if not user_profile:
        raise HTTPException(
            status_code=403,
            detail="Please complete your profile to access unlocked job feed",
        )

    # Parse query parameters or use profile values
    # State
    if state:
        state_list = [s.strip() for s in state.split(",") if s.strip()]
    else:
        # Use profile values
        if effective_user.role == "Contractor":
            state_list = user_profile.state if user_profile.state else []
        else:  # Supplier
            state_list = user_profile.service_states if user_profile.service_states else []
    
    # Country/City
    if country_city:
        country_city_list = [c.strip() for c in country_city.split(",") if c.strip()]
    else:
        # Use profile values
        country_city_list = user_profile.country_city if user_profile.country_city else []
    
    # User Type
    user_type_list = []
    if user_type:
        user_type_list = [ut.strip() for ut in user_type.split(",") if ut.strip()]

    # Get list of unlocked job IDs for this user
    unlocked_job_ids = (
        db.query(models.user.UnlockedLead.job_id)
        .filter(models.user.UnlockedLead.user_id == effective_user.id)
        .all()
    )
    unlocked_ids = [job_id[0] for job_id in unlocked_job_ids]

    # Build base query - only unlocked jobs that are posted
    base_query = db.query(models.user.Job).filter(
        models.user.Job.id.in_(unlocked_ids),
        models.user.Job.job_review_status == 'posted'
    )

    # If no unlocked jobs, return empty result
    if not unlocked_ids:
        return {
            "jobs": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
        }

    # Build search conditions based on user_type
    search_conditions = []

    # Match if ANY user_type in user_type_list matches ANY value in audience_type_slugs
    if user_type_list:
        audience_conditions = []
        for ut in user_type_list:
            audience_conditions.append(
                models.user.Job.audience_type_slugs.ilike(f"%{ut}%")
            )
        if audience_conditions:
            search_conditions.append(or_(*audience_conditions))

    # Apply user_type search conditions
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
            models.user.Job.source_county.ilike(f"%{city}%")
            for city in country_city_list
        ]
        base_query = base_query.filter(or_(*city_conditions))

    # Get all results for deduplication
    all_jobs = base_query.order_by(models.user.Job.review_posted_at.desc()).all()
    
    # Deduplicate jobs
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
    
    logger.info(f"/my-job-feed: {len(all_jobs)} jobs → {len(deduplicated_jobs)} unique ({len(all_jobs) - len(deduplicated_jobs)} duplicates removed)")
    
    # Apply pagination to deduplicated results
    offset = (page - 1) * page_size
    paginated_jobs = deduplicated_jobs[offset:offset + page_size]

    # Convert to response format (same as /jobs/feed endpoint)
    job_responses = [
        {
            "id": job.id,
            "trs_score": job.trs_score,
            "permit_type": job.permit_type,
            "country_city": job.country_city,
            "state": job.state,
            "project_description": job.project_description,
            "project_cost_total": job.project_cost_total,
            "property_type": job.property_type,
            "job_review_status": job.job_review_status,
            "job_cost": job.job_cost,
            "job_address": job.job_address,
            "review_posted_at": job.review_posted_at,
        }
        for job in paginated_jobs
    ]

    return {
        "jobs": job_responses,
        "total": len(deduplicated_jobs),
        "page": page,
        "page_size": page_size,
        "total_pages": (len(deduplicated_jobs) + page_size - 1) // page_size,
    }


@router.get("/all")
def get_all_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Get jobs matching user's profile (no filter overrides).

    For Contractors:
    - Matches jobs based on user_type array from contractor profile
    - Filters by states and country_city from profile

    For Suppliers:
    - Matches jobs based on user_type array from supplier profile
    - Filters by service_states and country_city from profile

    Always uses profile values - no parameter overrides.
    Returns paginated job results with TRS scores.
    Requires authentication token in header.
    """
    # Check user role
    if effective_user.role not in ["Contractor", "Supplier"]:
        raise HTTPException(
            status_code=403, detail="User must be a Contractor or Supplier"
        )

    # Get user profile
    if effective_user.role == "Contractor":
        user_profile = (
            db.query(models.user.Contractor)
            .filter(models.user.Contractor.user_id == effective_user.id)
            .first()
        )
    else:  # Supplier
        user_profile = (
            db.query(models.user.Supplier)
            .filter(models.user.Supplier.user_id == effective_user.id)
            .first()
        )

    if not user_profile:
        raise HTTPException(
            status_code=400,
            detail="Please complete your profile to see matched jobs",
        )
    # Get list of not-interested job IDs for this user
    not_interested_job_ids = (
        db.query(models.user.NotInterestedJob.job_id)
        .filter(models.user.NotInterestedJob.user_id == effective_user.id)
        .all()
    )
    not_interested_ids = [job_id[0] for job_id in not_interested_job_ids]

    # Get list of unlocked job IDs for this user
    unlocked_job_ids = (
        db.query(models.user.UnlockedLead.job_id)
        .filter(models.user.UnlockedLead.user_id == effective_user.id)
        .all()
    )
    unlocked_ids = [job_id[0] for job_id in unlocked_job_ids]

    # Get list of saved job IDs for this user
    saved_job_ids_rows = (
        db.query(models.user.SavedJob.job_id)
        .filter(models.user.SavedJob.user_id == effective_user.id)
        .all()
    )
    saved_ids = {job_id[0] for job_id in saved_job_ids_rows}

    # Combine excluded IDs (not-interested, unlocked, saved)
    excluded_ids = list(set(not_interested_ids + unlocked_ids + list(saved_ids)))

    # Always use profile values (no parameter overrides)
    # Get user type from profile
    if effective_user.role == "Contractor":
        user_types_raw = user_profile.user_type if user_profile.user_type else []
        state_list = user_profile.state if user_profile.state else []
    else:  # Supplier
        user_types_raw = user_profile.user_type if user_profile.user_type else []
        state_list = user_profile.service_states if user_profile.service_states else []
    
    # Country/City from profile
    country_city_list = user_profile.country_city if user_profile.country_city else []
    
    # Split comma-separated values within array elements for user_type
    user_type_list = []
    for item in user_types_raw:
        user_type_list.extend([ut.strip() for ut in item.split(",") if ut.strip()])
    
    # Build search conditions
    search_conditions = []
    
    # Match if ANY user_type matches ANY value in audience_type_slugs
    if user_type_list:
        audience_conditions = []
        for ut in user_type_list:
            audience_conditions.append(
                models.user.Job.audience_type_slugs.ilike(f"%{ut}%")
            )
        if audience_conditions:
            search_conditions.append(or_(*audience_conditions))


    # Build base query - FILTER FOR POSTED JOBS FIRST (same as /feed)
    base_query = db.query(models.user.Job).filter(
        models.user.Job.job_review_status == "posted"
    )

    # Exclude not-interested, unlocked, and saved jobs
    if excluded_ids:
        base_query = base_query.filter(~models.user.Job.id.in_(excluded_ids))

    # Apply user_type matching (OR within user types)
    if search_conditions:
        base_query = base_query.filter(or_(*search_conditions))

    # Filter by states (match ANY state in array) - OR within states
    if state_list and len(state_list) > 0:
        state_conditions = [
            models.user.Job.state.ilike(f"%{s}%") for s in state_list
        ]
        base_query = base_query.filter(or_(*state_conditions))

    # Filter by source_county (match ANY city/county in array) - OR within counties
    if country_city_list and len(country_city_list) > 0:
        city_conditions = [
            models.user.Job.source_county.ilike(f"%{city}%")
            for city in country_city_list
        ]
        base_query = base_query.filter(or_(*city_conditions))

    # Get all results ordered by TRS score for deduplication
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
    
    logger.info(f"/all: {len(all_jobs)} jobs → {len(deduplicated_jobs)} unique ({len(all_jobs) - len(deduplicated_jobs)} duplicates removed)")
    
    # Apply pagination to deduplicated results
    offset = (page - 1) * page_size
    paginated_jobs = deduplicated_jobs[offset:offset + page_size]

    # Convert to simplified response format
    job_responses = [
        {
            "id": job.id,
            "permit_type_norm": job.audience_type_names,  # Use audience_type_names for human-readable format
            "source_county": job.source_county,
            "state": job.state,
            "project_description": job.project_description,
            "project_cost_total": job.project_cost_total,
            "property_type": job.property_type,
            "job_review_status": job.job_review_status,
            "trs_score": job.trs_score,
            "review_posted_at": job.review_posted_at,
            "saved": job.id in saved_ids,
        }
        for job in paginated_jobs
    ]

    return {
        "jobs": job_responses,
        "total": len(deduplicated_jobs),
        "page": page,
        "page_size": page_size,
        "total_pages": (len(deduplicated_jobs) + page_size - 1) // page_size,
    }


@router.get("/search-saved-jobs")
def search_saved_jobs(
    keyword: str = Query(
        ..., min_length=1, description="Search keyword to match against job fields"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Search within user's saved jobs by keyword across job fields.

    Searches in:
    - Permit type
    - Project description
    - Job address
    - Permit status
    - Contractor email
    - Contractor phone
    - Country/city
    - State
    - Work type (slugs)
    - Work type (names)
    - Contractor name
    - Contractor company
    - Permit number

    Returns only jobs that user has saved, filtered by keyword.
    Returns paginated results ordered by saved date.
    """
    # Check user role
    if effective_user.role not in ["Contractor", "Supplier"]:
        raise HTTPException(
            status_code=403,
            detail="User must be a Contractor or Supplier"
        )

    # Get saved job IDs for this user
    saved_job_ids = (
        db.query(models.user.SavedJob.job_id)
        .filter(models.user.SavedJob.user_id == effective_user.id)
        .all()
    )
    saved_ids = [job_id[0] for job_id in saved_job_ids]

    if not saved_ids:
        return {
            "jobs": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
            "keyword": keyword,
        }

    # Build search query - keyword matches any field (case-insensitive)
    search_pattern = f"%{keyword.lower()}%"

    base_query = db.query(models.user.Job).filter(
        models.user.Job.id.in_(saved_ids),
        or_(
            models.user.Job.job_review_status.is_(None),
            models.user.Job.job_review_status == "posted",
        ),
        or_(
            func.lower(models.user.Job.permit_type_norm).like(search_pattern),
            func.lower(models.user.Job.project_description).like(search_pattern),
            func.lower(models.user.Job.job_address).like(search_pattern),
            func.lower(models.user.Job.permit_status).like(search_pattern),
            func.lower(models.user.Job.contractor_email).like(search_pattern),
            func.lower(models.user.Job.contractor_phone).like(search_pattern),
            func.lower(models.user.Job.source_county).like(search_pattern),
            func.lower(models.user.Job.state).like(search_pattern),
            func.lower(models.user.Job.audience_type_slugs).like(search_pattern),
            func.lower(models.user.Job.contractor_name).like(search_pattern),
            func.lower(models.user.Job.contractor_company).like(search_pattern),
            func.lower(models.user.Job.permit_number).like(search_pattern),
            func.lower(models.user.Job.audience_type_names).like(search_pattern),
        ),
    )

    # Get all results ordered for deduplication
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
    
    logger.info(f"/search-saved-jobs: {len(all_jobs)} jobs → {len(deduplicated_jobs)} unique ({len(all_jobs) - len(deduplicated_jobs)} duplicates removed)")
    
    # Apply pagination to deduplicated results
    offset = (page - 1) * page_size
    paginated_jobs = deduplicated_jobs[offset:offset + page_size]

    # Convert to simplified response format
    job_responses = [
        {
            "id": job.id,
            "trs_score": job.trs_score,
            "permit_type": job.permit_type,
            "country_city": job.country_city,
            "state": job.state,
            "project_description": job.project_description,
            "project_cost_total": job.project_cost_total,
            "property_type": job.property_type,
            "job_review_status": job.job_review_status,
            "review_posted_at": job.review_posted_at,
            "saved": True,  # All results are saved jobs
        }
        for job in paginated_jobs
    ]

    return {
        "jobs": job_responses,
        "total": len(deduplicated_jobs),
        "page": page,
        "page_size": page_size,
        "total_pages": (len(deduplicated_jobs) + page_size - 1) // page_size,
        "keyword": keyword,
    }


@router.get("/search-my-jobs")
def search_my_jobs(
    keyword: str = Query(
        ..., min_length=1, description="Search keyword to match against job fields"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Search within user's unlocked jobs (my jobs) by keyword across job fields.

    Searches in:
    - Permit type
    - Project description
    - Job address
    - Permit status
    - Contractor email
    - Contractor phone
    - Country/city
    - State
    - Work type (slugs)
    - Work type (names)
    - Contractor name
    - Contractor company
    - Permit number

    Returns only jobs that user has unlocked (paid credits for), filtered by keyword.
    Returns paginated results ordered by unlock date.
    """
    # Check user role
    if effective_user.role not in ["Contractor", "Supplier"]:
        raise HTTPException(
            status_code=403,
            detail="User must be a Contractor or Supplier"
        )

    # Get unlocked job IDs for this user
    unlocked_job_ids = (
        db.query(models.user.UnlockedLead.job_id)
        .filter(models.user.UnlockedLead.user_id == effective_user.id)
        .all()
    )
    unlocked_ids = [job_id[0] for job_id in unlocked_job_ids]

    if not unlocked_ids:
        return {
            "jobs": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
            "keyword": keyword,
        }

    # Get saved job IDs to mark saved status
    saved_job_ids = (
        db.query(models.user.SavedJob.job_id)
        .filter(models.user.SavedJob.user_id == effective_user.id)
        .all()
    )
    saved_ids = {job_id[0] for job_id in saved_job_ids}

    # Build search query - keyword matches any field (case-insensitive)
    search_pattern = f"%{keyword.lower()}%"

    base_query = db.query(models.user.Job).filter(
        models.user.Job.id.in_(unlocked_ids),
        or_(
            models.user.Job.job_review_status.is_(None),
            models.user.Job.job_review_status == "posted",
        ),
        or_(
            func.lower(models.user.Job.permit_type_norm).like(search_pattern),
            func.lower(models.user.Job.project_description).like(search_pattern),
            func.lower(models.user.Job.job_address).like(search_pattern),
            func.lower(models.user.Job.permit_status).like(search_pattern),
            func.lower(models.user.Job.contractor_email).like(search_pattern),
            func.lower(models.user.Job.contractor_phone).like(search_pattern),
            func.lower(models.user.Job.source_county).like(search_pattern),
            func.lower(models.user.Job.state).like(search_pattern),
            func.lower(models.user.Job.audience_type_slugs).like(search_pattern),
            func.lower(models.user.Job.contractor_name).like(search_pattern),
            func.lower(models.user.Job.contractor_company).like(search_pattern),
            func.lower(models.user.Job.permit_number).like(search_pattern),
            func.lower(models.user.Job.audience_type_names).like(search_pattern),
        ),
    )

    # Get all results ordered for deduplication
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
    
    logger.info(f"/search-my-jobs: {len(all_jobs)} jobs → {len(deduplicated_jobs)} unique ({len(all_jobs) - len(deduplicated_jobs)} duplicates removed)")
    
    # Apply pagination to deduplicated results
    offset = (page - 1) * page_size
    paginated_jobs = deduplicated_jobs[offset:offset + page_size]

    # Convert to simplified response format
    job_responses = [
        {
            "id": job.id,
            "trs_score": job.trs_score,
            "permit_type": job.permit_type,
            "country_city": job.country_city,
            "state": job.state,
            "project_description": job.project_description,
            "project_cost_total": job.project_cost_total,
            "property_type": job.property_type,
            "job_review_status": job.job_review_status,
            "review_posted_at": job.review_posted_at,
            "saved": job.id in saved_ids,
        }
        for job in paginated_jobs
    ]

    return {
        "jobs": job_responses,
        "total": len(deduplicated_jobs),
        "page": page,
        "page_size": page_size,
        "total_pages": (len(deduplicated_jobs) + page_size - 1) // page_size,
        "keyword": keyword,
    }


@router.get("/search")
def search_jobs(
    keyword: str = Query(
        ..., min_length=1, description="Search keyword to match against job fields"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Search jobs by keyword across job fields, filtered by user's location preferences.

    Searches in:
    - Permit type
    - Project description
    - Job address
    - Permit status
    - Contractor email
    - Contractor phone
    - Country/city
    - State
    - Work type (slugs)
    - Work type (names)
    - Contractor name
    - Contractor company
    - Permit number

    Filters jobs to match user's state and country_city from their profile.
    Excludes jobs user marked as not interested and already unlocked jobs.
    Returns paginated results ordered by TRS score.
    """
    # Check user role and get profile
    if effective_user.role not in ["Contractor", "Supplier"]:
        raise HTTPException(
            status_code=403,
            detail="User must be a Contractor or Supplier"
        )

    # Get user profile to access location preferences
    user_profile = None
    if effective_user.role == "Contractor":
        user_profile = (
            db.query(models.user.Contractor)
            .filter(models.user.Contractor.user_id == effective_user.id)
            .first()
        )
    else:  # Supplier
        user_profile = (
            db.query(models.user.Supplier)
            .filter(models.user.Supplier.user_id == effective_user.id)
            .first()
        )

    if not user_profile:
        raise HTTPException(
            status_code=400,
            detail="Please complete your profile to search jobs"
        )

    # Get user's states and cities from profile
    if effective_user.role == "Contractor":
        user_states = user_profile.state if user_profile.state else []
        user_country_cities = user_profile.country_city if user_profile.country_city else []
    else:  # Supplier
        user_states = user_profile.service_states if user_profile.service_states else []
        user_country_cities = user_profile.country_city if user_profile.country_city else []

    # Get excluded job IDs
    not_interested_job_ids = (
        db.query(models.user.NotInterestedJob.job_id)
        .filter(models.user.NotInterestedJob.user_id == effective_user.id)
        .all()
    )
    not_interested_ids = [job_id[0] for job_id in not_interested_job_ids]

    unlocked_job_ids = (
        db.query(models.user.UnlockedLead.job_id)
        .filter(models.user.UnlockedLead.user_id == effective_user.id)
        .all()
    )
    unlocked_ids = [job_id[0] for job_id in unlocked_job_ids]

    # Get list of saved job IDs for this user so we can mark saved state
    saved_job_ids = (
        db.query(models.user.SavedJob.job_id)
        .filter(models.user.SavedJob.user_id == effective_user.id)
        .all()
    )
    saved_ids = {job_id[0] for job_id in saved_job_ids}

    # Exclude not-interested, unlocked, and saved jobs
    excluded_ids = list(set(not_interested_ids + unlocked_ids + list(saved_ids)))

    # Build search query - keyword matches any field (case-insensitive)
    search_pattern = f"%{keyword.lower()}%"

    base_query = db.query(models.user.Job).filter(
        or_(
            models.user.Job.job_review_status.is_(None),
            models.user.Job.job_review_status == "posted",
        ),
        or_(
            func.lower(models.user.Job.permit_type_norm).like(search_pattern),
            func.lower(models.user.Job.project_description).like(search_pattern),
            func.lower(models.user.Job.job_address).like(search_pattern),
            func.lower(models.user.Job.permit_status).like(search_pattern),
            func.lower(models.user.Job.contractor_email).like(search_pattern),
            func.lower(models.user.Job.contractor_phone).like(search_pattern),
            func.lower(models.user.Job.source_county).like(search_pattern),
            func.lower(models.user.Job.state).like(search_pattern),
            func.lower(models.user.Job.audience_type_slugs).like(search_pattern),
            func.lower(models.user.Job.contractor_name).like(search_pattern),
            func.lower(models.user.Job.contractor_company).like(search_pattern),
            func.lower(models.user.Job.permit_number).like(search_pattern),
            func.lower(models.user.Job.audience_type_names).like(search_pattern),
        ),
    )

    # Filter by user's states (match ANY state from user's profile)
    if user_states and len(user_states) > 0:
        state_conditions = [
            models.user.Job.state.ilike(f"%{state}%") for state in user_states
        ]
        base_query = base_query.filter(or_(*state_conditions))

    # Filter by user's country_city (match ANY city/county from user's profile)
    if user_country_cities and len(user_country_cities) > 0:
        city_conditions = [
            models.user.Job.source_county.ilike(f"%{city}%")
            for city in user_country_cities
        ]
        base_query = base_query.filter(or_(*city_conditions))

    # Exclude not-interested and unlocked jobs
    if excluded_ids:
        base_query = base_query.filter(~models.user.Job.id.in_(excluded_ids))

    # Get all results ordered for deduplication
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
    
    logger.info(f"/search: {len(all_jobs)} jobs → {len(deduplicated_jobs)} unique ({len(all_jobs) - len(deduplicated_jobs)} duplicates removed)")
    
    # Apply pagination to deduplicated results
    offset = (page - 1) * page_size
    paginated_jobs = deduplicated_jobs[offset:offset + page_size]

    # Convert to simplified response format
    job_responses = [
        {
            "id": job.id,
            "trs_score": job.trs_score,
            "permit_type": job.permit_type,
            "country_city": job.country_city,
            "state": job.state,
            "project_description": job.project_description,
            "project_cost_total": job.project_cost_total,
            "property_type": job.property_type,
            "job_review_status": job.job_review_status,
            "review_posted_at": job.review_posted_at,
            "saved": job.id in saved_ids,
        }
        for job in paginated_jobs
    ]

    return {
        "jobs": job_responses,
        "total": len(deduplicated_jobs),
        "page": page,
        "page_size": page_size,
        "total_pages": (len(deduplicated_jobs) + page_size - 1) // page_size,
        "keyword": keyword,
    }


@router.get("/my-unlocked-leads")
def get_my_unlocked_leads(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    """Get all unlocked leads for the current user."""
    # Get total count
    total = (
        db.query(models.user.UnlockedLead)
        .filter(models.user.UnlockedLead.user_id == effective_user.id)
        .count()
    )

    # Get all unlocked leads with job details for deduplication
    all_unlocked_leads = (
        db.query(models.user.UnlockedLead, models.user.Job)
        .join(models.user.Job, models.user.UnlockedLead.job_id == models.user.Job.id)
        .filter(
            models.user.UnlockedLead.user_id == effective_user.id,
            models.user.Job.job_review_status == 'posted'
        )
        .order_by(models.user.UnlockedLead.unlocked_at.desc())
        .all()
    )
    
    # Deduplicate by job details
    seen_jobs = set()
    deduplicated_leads = []
    
    for lead, job in all_unlocked_leads:
        job_key = (
            (job.permit_type_norm or "").lower().strip(),
            (job.project_description or "").lower().strip()[:200],
            (job.contractor_name or "").lower().strip(),
            (job.contractor_email or "").lower().strip()
        )
        
        if job_key not in seen_jobs:
            seen_jobs.add(job_key)
            deduplicated_leads.append((lead, job))
    
    logger.info(f"/my-unlocked-leads: {len(all_unlocked_leads)} leads → {len(deduplicated_leads)} unique ({len(all_unlocked_leads) - len(deduplicated_leads)} duplicates removed)")
    
    # Apply pagination to deduplicated results
    offset = (page - 1) * page_size
    paginated_leads = deduplicated_leads[offset:offset + page_size]

    leads_response = [
        {
            "unlocked_lead_id": lead.id,
            "job_id": job.id,
            "permit_record_number": job.permit_number,  # Fixed: was permit_record_number
            "date": job.created_at,  # Fixed: was date
            "permit_type": job.audience_type_names,  # Use audience_type_names for human-readable format
            "project_description": job.project_description,
            "job_address": job.job_address,
            "job_cost": job.job_cost,  # This is a property alias for project_cost_total
            "permit_status": job.permit_status,
            "email": job.email,  # This is a property alias for contractor_email
            "phone_number": job.phone_number,  # This is a property alias for contractor_phone
            "country_city": job.country_city,  # This is a property alias for source_county
            "state": job.state,
            "property_type": job.property_type,
            "work_type": job.audience_type_names,  # Fixed: was work_type
            "credits_spent": lead.credits_spent,
            "unlocked_at": lead.unlocked_at,
        }
        for lead, job in paginated_leads
    ]

    return {
        "unlocked_leads": leads_response,
        "total": len(deduplicated_leads),
        "page": page,
        "page_size": page_size,
        "total_pages": (len(deduplicated_leads) + page_size - 1) // page_size,
    }


@router.get("/export-unlocked-leads")
def export_unlocked_leads(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """Export all unlocked leads to Excel file."""
    # Get all unlocked leads with job details - only posted jobs
    unlocked_leads = (
        db.query(models.user.UnlockedLead, models.user.Job)
        .join(models.user.Job, models.user.UnlockedLead.job_id == models.user.Job.id)
        .filter(
            models.user.UnlockedLead.user_id == effective_user.id,
            models.user.Job.job_review_status == 'posted'
        )
        .order_by(models.user.UnlockedLead.unlocked_at.desc())
        .all()
    )

    # Create DataFrame
    data = []
    for lead, job in unlocked_leads:
        data.append(
            {
                "Permit Number": job.permit_number,
                "Permit Type": job.permit_type,
                "Permit Type Normalized": job.audience_type_names,  # Use audience_type_names for human-readable format
                "Permit Status": job.permit_status,
                "Job Cost": job.job_cost,
                "Job Address": job.job_address,
                "Country/City": job.country_city,
                "State": job.state,
                "Project Description": job.project_description,
                "Project Cost Total": job.project_cost_total,
                "Property Type": job.property_type,
                "Job Review Status": job.job_review_status,
                "Email": job.email,
                "Phone Number": job.phone_number,
                "Contractor Email": job.contractor_email,
                "Contractor Phone": job.contractor_phone,
                "Applicant Email": job.applicant_email,
                "Applicant Phone": job.applicant_phone,
                "Notes": lead.notes,
            }
        )

    df = pd.DataFrame(data)

    # Create Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Unlocked Leads")

    output.seek(0)

    # Return as streaming response
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=unlocked_leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        },
    )


@router.get("/matched-jobs-contractor", response_model=schemas.PaginatedJobResponse)
async def get_matched_jobs_contractor(
    db: Session = Depends(get_db),
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
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

    # Check if main account is a contractor
    if effective_user.role != "Contractor":
        raise HTTPException(
            status_code=403,
            detail="Only contractors can access matched jobs. Please complete your contractor profile.",
        )

    # Get contractor profile
    contractor = (
        db.query(models.user.Contractor)
        .filter(models.user.Contractor.user_id == effective_user.id)
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

    # Build search conditions for all selected trade categories
    search_conditions = []

    if trade_categories:
        audience_conditions = []
        for category in trade_categories:
            audience_conditions.append(
                models.user.Job.audience_type_slugs.ilike(f"%{category}%")
            )
        if audience_conditions:
            search_conditions.append(or_(*audience_conditions))

    # Combine all category conditions with OR (job matches if it matches ANY category)
    # Only show posted jobs
    base_query = db.query(models.user.Job).filter(
        models.user.Job.job_review_status == 'posted'
    )

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
            models.user.Job.source_county.ilike(f"%{city}%")
            for city in contractor_country_cities
        ]
        base_query = base_query.filter(or_(*city_conditions))

    # Get total count
    total_count = base_query.count()

    # Get all results, ordered by TRS score descending
    jobs = base_query.order_by(
        models.user.Job.trs_score.desc(), models.user.Job.created_at.desc()
    ).all()
    
    # Deduplicate jobs by (permit_type_norm, project_description, contractor_name, contractor_email)
    # Keep first occurrence (highest TRS score)
    seen_jobs = set()
    deduplicated_jobs = []
    
    for job in jobs:
        # Create unique key from critical fields
        job_key = (
            (job.permit_type_norm or "").lower().strip(),
            (job.project_description or "").lower().strip()[:200],  # First 200 chars
            (job.contractor_name or "").lower().strip(),
            (job.contractor_email or "").lower().strip()
        )
        
        if job_key not in seen_jobs:
            seen_jobs.add(job_key)
            deduplicated_jobs.append(job)
            logger.debug(f"Kept job {job.id}: {job.contractor_name} - {job.permit_type_norm}")
        else:
            logger.debug(f"Skipped duplicate job {job.id}: {job.contractor_name} - {job.permit_type_norm}")
    
    logger.info(f"Deduplication: {len(jobs)} jobs → {len(deduplicated_jobs)} unique jobs ({len(jobs) - len(deduplicated_jobs)} duplicates removed)")
    
    # Also get saved job ids so we can mark saved state when rendering jobs
    saved_job_ids = (
        db.query(models.user.SavedJob.job_id)
        .filter(models.user.SavedJob.user_id == effective_user.id)
        .all()
    )
    saved_ids = {job_id[0] for job_id in saved_job_ids}

    # Convert to response schema
    job_responses = []
    for job in deduplicated_jobs:  # Use deduplicated list
        # Check if current user has unlocked this job
        unlocked_lead = (
            db.query(models.user.UnlockedLead)
            .filter(
                models.user.UnlockedLead.user_id == effective_user.id,
                models.user.UnlockedLead.job_id == job.id,
            )
            .first()
        )

        job_responses.append(
            schemas.JobResponse(
                id=job.id,
                permit_number=job.permit_number,
                permit_status=job.permit_status,
                permit_type_norm=job.permit_type_norm,
                job_address=job.job_address,
                project_description=job.project_description,
                project_cost_total=job.project_cost_total,
                source_county=job.source_county,
                state=job.state,
                contractor_name=job.contractor_name,
                contractor_company=job.contractor_company,
                contractor_email=job.contractor_email if unlocked_lead else None,
                contractor_phone=job.contractor_phone if unlocked_lead else None,
                audience_type_names=job.audience_type_names,
                property_type=job.property_type,
                job_review_status=job.job_review_status,
                review_posted_at=job.review_posted_at,
                trs_score=job.trs_score,
                is_unlocked=unlocked_lead is not None,
                saved=(job.id in saved_ids),
                created_at=job.created_at,
                updated_at=job.updated_at,
            )
        )

    return schemas.PaginatedJobResponse(
        jobs=job_responses,
        total=len(deduplicated_jobs),  # Use deduplicated count
        page=1,
        page_size=len(deduplicated_jobs),
        total_pages=1,
    )


@router.get("/matched-jobs-supplier", response_model=schemas.PaginatedJobResponse)
async def get_matched_jobs_supplier(
    db: Session = Depends(get_db),
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
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

    # Check if main account is a supplier
    if effective_user.role != "Supplier":
        raise HTTPException(
            status_code=403,
            detail="Only suppliers can access matched jobs. Please complete your supplier profile.",
        )

    # Get supplier profile
    supplier = (
        db.query(models.user.Supplier)
        .filter(models.user.Supplier.user_id == effective_user.id)
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

    # Build search conditions for all selected product categories
    search_conditions = []

    if product_categories:
        audience_conditions = []
        for category in product_categories:
            audience_conditions.append(
                models.user.Job.audience_type_slugs.ilike(f"%{category}%")
            )
        if audience_conditions:
            search_conditions.append(or_(*audience_conditions))

    # Combine all category conditions with OR (job matches if it matches ANY category)
    # Only show posted jobs
    base_query = db.query(models.user.Job).filter(
        models.user.Job.job_review_status == 'posted'
    )

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
            models.user.Job.source_county.ilike(f"%{city}%")
            for city in supplier_country_cities
        ]
        base_query = base_query.filter(or_(*city_conditions))

    # Get all results, ordered by TRS score descending
    jobs = base_query.order_by(
        models.user.Job.trs_score.desc(), models.user.Job.created_at.desc()
    ).all()
    
    # Deduplicate jobs by (permit_type_norm, project_description, contractor_name, contractor_email)
    seen_jobs = set()
    deduplicated_jobs = []
    
    for job in jobs:
        job_key = (
            (job.permit_type_norm or "").lower().strip(),
            (job.project_description or "").lower().strip()[:200],
            (job.contractor_name or "").lower().strip(),
            (job.contractor_email or "").lower().strip()
        )
        
        if job_key not in seen_jobs:
            seen_jobs.add(job_key)
            deduplicated_jobs.append(job)
            logger.debug(f"Kept job {job.id}: {job.contractor_name} - {job.permit_type_norm}")
        else:
            logger.debug(f"Skipped duplicate job {job.id}: {job.contractor_name} - {job.permit_type_norm}")
    
    logger.info(f"/matched-jobs-supplier: {len(jobs)} jobs → {len(deduplicated_jobs)} unique ({len(jobs) - len(deduplicated_jobs)} duplicates removed)")

    # Also get saved job ids so we can mark saved state when rendering jobs
    saved_job_ids = (
        db.query(models.user.SavedJob.job_id)
        .filter(models.user.SavedJob.user_id == effective_user.id)
        .all()
    )
    saved_ids = {job_id[0] for job_id in saved_job_ids}

    # Convert to response schema
    job_responses = []
    for job in deduplicated_jobs:  # Use deduplicated list
        # Check if current user has unlocked this job
        unlocked_lead = (
            db.query(models.user.UnlockedLead)
            .filter(
                models.user.UnlockedLead.user_id == effective_user.id,
                models.user.UnlockedLead.job_id == job.id,
            )
            .first()
        )

        job_responses.append(
            schemas.JobResponse(
                id=job.id,
                permit_number=job.permit_number,
                permit_status=job.permit_status,
                permit_type_norm=job.permit_type_norm,
                job_address=job.job_address,
                project_description=job.project_description,
                project_cost_total=job.project_cost_total,
                source_county=job.source_county,
                state=job.state,
                contractor_name=job.contractor_name,
                contractor_company=job.contractor_company,
                contractor_email=job.contractor_email if unlocked_lead else None,
                contractor_phone=job.contractor_phone if unlocked_lead else None,
                audience_type_names=job.audience_type_names,
                property_type=job.property_type,
                job_review_status=job.job_review_status,
                review_posted_at=job.review_posted_at,
                trs_score=job.trs_score,
                is_unlocked=unlocked_lead is not None,
                saved=(job.id in saved_ids),
                created_at=job.created_at,
                updated_at=job.updated_at,
            )
        )

    return schemas.PaginatedJobResponse(
        jobs=job_responses,
        total=len(deduplicated_jobs),  # Use deduplicated count
        page=1,
        page_size=len(deduplicated_jobs),
        total_pages=1,
    )
