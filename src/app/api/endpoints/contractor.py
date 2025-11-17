import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.app import models, schemas
from src.app.api.deps import get_current_user
from src.app.core.database import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contractor", tags=["Contractor"])

# Allowed file extensions
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/step-1", response_model=schemas.ContractorStepResponse)
def contractor_step_1(
    data: schemas.ContractorStep1,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Step 1 of 4: Basic Business Information

    Requires authentication token in header.
    User must have role set to 'Contractor'.
    """
    logger.info(f"Step 1 request from user: {current_user.email}")

    # Verify user has contractor role
    if current_user.role != "Contractor":
        logger.warning(
            f"User {current_user.email} attempted contractor registration without Contractor role"
        )
        raise HTTPException(
            status_code=403,
            detail="You must set your role to 'Contractor' before registering as a contractor",
        )

    try:
        # Get existing contractor profile (create only here if missing)
        contractor = (
            db.query(models.user.Contractor)
            .filter(models.user.Contractor.user_id == current_user.id)
            .first()
        )

        if not contractor:
            logger.info(
                f"Creating new contractor profile for user_id: {current_user.id}"
            )
            contractor = models.user.Contractor(
                user_id=current_user.id,
                registration_step=0,
                is_completed=False,
            )
            db.add(contractor)
            db.commit()
            db.refresh(contractor)
            logger.info(f"Contractor profile created with id: {contractor.id}")

        # Update Step 1 data
        contractor.company_name = data.company_name
        contractor.primary_contact_name = data.primary_contact_name
        contractor.phone_number = data.phone_number
        contractor.website_url = data.website_url
        contractor.business_address = data.business_address
        contractor.business_type = data.business_type
        contractor.years_in_business = data.years_in_business

        # Update registration step
        if contractor.registration_step < 1:
            contractor.registration_step = 1

        db.add(contractor)
        db.commit()
        db.refresh(contractor)

        logger.info(f"Step 1 completed for contractor id: {contractor.id}")

        return {
            "message": "Basic business information saved successfully",
            "step_completed": 1,
            "total_steps": 4,
            "is_completed": False,
            "next_step": 2,
        }

    except Exception as e:
        logger.error(f"Error in contractor step 1 for user {current_user.id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500, detail="Failed to save business information"
        )


@router.post("/step-2", response_model=schemas.ContractorStepResponse)
async def contractor_step_2(
    state_license_number: str,
    license_expiration_date: str,
    license_status: str,
    license_picture: UploadFile = File(...),
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Step 2 of 4: License Information

    Requires authentication token in header.
    User must have completed Step 1.
    Upload license picture directly (JPG, JPEG, PNG - max 10MB)
    """
    logger.info(f"Step 2 request from user: {current_user.email}")

    # Verify user has contractor role
    if current_user.role != "Contractor":
        raise HTTPException(status_code=403, detail="Contractor role required")

    try:
        # Get contractor profile
        contractor = (
            db.query(models.user.Contractor)
            .filter(models.user.Contractor.user_id == current_user.id)
            .first()
        )

        if not contractor:
            raise HTTPException(status_code=400, detail="Please complete Step 1 first")

        if contractor.registration_step < 1:
            raise HTTPException(
                status_code=400,
                detail="Please complete Step 1 before proceeding to Step 2",
            )

        # Validate and upload license picture
        if not license_picture or not license_picture.filename:
            raise HTTPException(
                status_code=400, detail="License picture file is required"
            )

        file_ext = Path(license_picture.filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type '{file_ext}'. Only image files are allowed: JPG, JPEG, PNG, or PDF",
            )

        # Read and validate file size
        contents = await license_picture.read()
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE / (1024*1024)}MB",
            )

        # Determine content type
        content_type = license_picture.content_type or "image/jpeg"

        logger.info(
            f"License picture received: {license_picture.filename}, size: {len(contents)} bytes"
        )

        # Parse date - try multiple formats
        expiry_date = None
        for date_format in ["%Y-%m-%d", "%m-%d-%Y", "%d-%m-%Y"]:
            try:
                expiry_date = datetime.strptime(
                    license_expiration_date, date_format
                ).date()
                break
            except ValueError:
                continue

        if not expiry_date:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Use YYYY-MM-DD, MM-DD-YYYY, or DD-MM-YYYY",
            )

        # Update Step 2 data - Store binary data in database
        contractor.state_license_number = state_license_number
        contractor.license_picture = contents  # Store binary data
        contractor.license_picture_filename = license_picture.filename
        contractor.license_picture_content_type = content_type
        contractor.license_expiration_date = expiry_date
        contractor.license_status = license_status

        # Update registration step
        if contractor.registration_step < 2:
            contractor.registration_step = 2

        db.add(contractor)
        db.commit()
        db.refresh(contractor)

        logger.info(f"Step 2 completed for contractor id: {contractor.id}")

        return {
            "message": "License information saved successfully",
            "step_completed": 2,
            "total_steps": 4,
            "is_completed": False,
            "next_step": 3,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in contractor step 2 for user {current_user.id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500, detail="Failed to save license information"
        )


@router.post("/step-3", response_model=schemas.ContractorStepResponse)
def contractor_step_3(
    data: schemas.ContractorStep3,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Step 3 of 4: Trade Information

    Requires authentication token in header.
    User can select up to 5 business types.
    """
    logger.info(f"Step 3 request from user: {current_user.email}")
    logger.info(
        f"Step 3 data received: work_type={data.work_type}, business_types={data.business_types}"
    )

    # Verify user has contractor role
    if current_user.role != "Contractor":
        logger.error(f"User {current_user.email} does not have Contractor role")
        raise HTTPException(status_code=403, detail="Contractor role required")

    try:
        # Get contractor profile
        contractor = (
            db.query(models.user.Contractor)
            .filter(models.user.Contractor.user_id == current_user.id)
            .first()
        )

        if not contractor:
            raise HTTPException(status_code=400, detail="Please complete Step 1 first")

        if contractor.registration_step < 2:
            raise HTTPException(
                status_code=400,
                detail="Please complete Step 2 before proceeding to Step 3",
            )

        # Update Step 3 data
        contractor.work_type = data.work_type
        # Store business_types as JSON string
        contractor.business_types = json.dumps(data.business_types)

        # Update registration step
        if contractor.registration_step < 3:
            contractor.registration_step = 3

        db.add(contractor)
        db.commit()
        db.refresh(contractor)

        logger.info(f"Step 3 completed for contractor id: {contractor.id}")

        return {
            "message": "Trade information saved successfully",
            "step_completed": 3,
            "total_steps": 4,
            "is_completed": False,
            "next_step": 4,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in contractor step 3 for user {current_user.id}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save trade information")


@router.post("/step-4", response_model=schemas.ContractorStepResponse)
def contractor_step_4(
    data: schemas.ContractorStep4,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Step 4 of 4: Service Jurisdictions

    Requires authentication token in header.
    This is the final step of contractor registration.
    """
    logger.info(f"Step 4 (Final) request from user: {current_user.email}")

    # Verify user has contractor role
    if current_user.role != "Contractor":
        raise HTTPException(status_code=403, detail="Contractor role required")

    try:
        # Get contractor profile
        contractor = (
            db.query(models.user.Contractor)
            .filter(models.user.Contractor.user_id == current_user.id)
            .first()
        )

        if not contractor:
            raise HTTPException(status_code=400, detail="Please complete Step 1 first")

        if contractor.registration_step < 3:
            raise HTTPException(
                status_code=400,
                detail="Please complete Step 3 before proceeding to Step 4",
            )

        # Update Step 4 data
        contractor.service_state = data.service_state
        contractor.service_zip_code = data.service_zip_code

        # Mark registration as completed
        contractor.registration_step = 4
        contractor.is_completed = True

        db.add(contractor)
        db.commit()
        db.refresh(contractor)

        logger.info(f"Contractor registration completed for id: {contractor.id}")

        return {
            "message": "Contractor registration completed successfully! Your profile is now active.",
            "step_completed": 4,
            "total_steps": 4,
            "is_completed": True,
            "next_step": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in contractor step 4 for user {current_user.id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500, detail="Failed to save service jurisdiction information"
        )


@router.get("/profile", response_model=schemas.ContractorProfile)
def get_contractor_profile(
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the contractor profile for the authenticated user.

    Requires authentication token in header.
    """
    logger.info(f"Profile request from user: {current_user.email}")

    # Verify user has contractor role
    if current_user.role != "Contractor":
        raise HTTPException(
            status_code=403,
            detail="Only users with Contractor role can access contractor profiles",
        )

    contractor = (
        db.query(models.user.Contractor)
        .filter(models.user.Contractor.user_id == current_user.id)
        .first()
    )

    if not contractor:
        raise HTTPException(
            status_code=404,
            detail="Contractor profile not found. Please complete Step 1 to create your profile.",
        )

    return contractor


