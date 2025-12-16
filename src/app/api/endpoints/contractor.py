import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
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

        # Update Step 1 data dynamically
        # This approach automatically handles any new fields added to the model
        for field_name, field_value in data.model_dump().items():
            if hasattr(contractor, field_name):
                setattr(contractor, field_name, field_value)

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
    state_license_number: str = Form(...),
    license_expiration_date: str = Form(...),
    license_status: str = Form(...),
    license_picture: UploadFile = File(None),
    referrals: UploadFile = File(None),
    job_photos: UploadFile = File(None),
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Step 2 of 4: License Information

    Requires authentication token in header.
    User must have completed Step 1.
    All fields must be submitted as multipart/form-data:
    - state_license_number, license_expiration_date, license_status as text fields
    - license_picture as file (JPG, JPEG, PNG, PDF - max 10MB) - OPTIONAL
    - referrals as file (JPG, JPEG, PNG, PDF - max 10MB) - OPTIONAL
    - job_photos as file (JPG, JPEG, PNG, PDF - max 10MB) - OPTIONAL
    """
    logger.info(
        "Step 2 request from user: %s | state_license_number=%s | "
        "license_expiration_date=%s | license_status=%s",
        current_user.email,
        state_license_number,
        license_expiration_date,
        license_status,
    )

    # Verify user has contractor role
    if current_user.role != "Contractor":
        logger.warning(
            "Step 2: user %s attempted access without Contractor role (role=%s)",
            current_user.email,
            current_user.role,
        )
        raise HTTPException(status_code=403, detail="Contractor role required")

    try:
        # Get contractor profile
        contractor = (
            db.query(models.user.Contractor)
            .filter(models.user.Contractor.user_id == current_user.id)
            .first()
        )

        if not contractor:
            logger.warning(
                "Step 2: contractor profile not found for user_id=%s. "
                "User must complete Step 1 first.",
                current_user.id,
            )
            raise HTTPException(status_code=400, detail="Please complete Step 1 first")

        if contractor.registration_step < 1:
            logger.warning(
                "Step 2: user_id=%s has registration_step=%s. "
                "Step 1 must be completed before Step 2.",
                current_user.id,
                contractor.registration_step,
            )
            raise HTTPException(
                status_code=400,
                detail="Please complete Step 1 before proceeding to Step 2",
            )

        # Helper function to process file uploads
        async def process_file_upload(file: UploadFile, file_type: str):
            if not file or not file.filename:
                logger.info("Step 2: %s not provided or empty", file_type)
                return None

            file_ext = Path(file.filename).suffix.lower()
            if file_ext not in ALLOWED_EXTENSIONS:
                logger.warning(
                    "Step 2: invalid file type for %s. filename=%s, ext=%s",
                    file_type,
                    file.filename,
                    file_ext,
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file type '{file_ext}' for {file_type}. Only JPG, JPEG, PNG, or PDF allowed",
                )

            # Read and validate file size
            contents = await file.read()
            if len(contents) > MAX_FILE_SIZE:
                logger.warning(
                    "Step 2: %s file too large. filename=%s, size_bytes=%s",
                    file_type,
                    file.filename,
                    len(contents),
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"{file_type} file too large. Maximum size: {MAX_FILE_SIZE / (1024*1024)}MB",
                )

            # Determine content type
            content_type = file.content_type or "image/jpeg"

            logger.info(
                "Step 2: %s received. filename=%s, size_bytes=%s, content_type=%s",
                file_type,
                file.filename,
                len(contents),
                content_type,
            )

            return {
                "contents": contents,
                "filename": file.filename,
                "content_type": content_type,
            }

        # Process license picture if provided
        license_data = await process_file_upload(license_picture, "License picture")
        if license_data:
            contractor.license_picture = license_data["contents"]
            contractor.license_picture_filename = license_data["filename"]
            contractor.license_picture_content_type = license_data["content_type"]

        # Process referrals if provided
        referrals_data = await process_file_upload(referrals, "Referrals")
        if referrals_data:
            contractor.referrals = referrals_data["contents"]
            contractor.referrals_filename = referrals_data["filename"]
            contractor.referrals_content_type = referrals_data["content_type"]

        # Process job photos if provided
        job_photos_data = await process_file_upload(job_photos, "Job photos")
        if job_photos_data:
            contractor.job_photos = job_photos_data["contents"]
            contractor.job_photos_filename = job_photos_data["filename"]
            contractor.job_photos_content_type = job_photos_data["content_type"]

        # Parse date - try multiple formats
        expiry_date = None
        for date_format in ["%Y-%m-%d", "%m-%d-%Y", "%d-%m-%Y"]:
            try:
                expiry_date = datetime.strptime(
                    license_expiration_date, date_format
                ).date()
                logger.info(
                    "Step 2: parsed license_expiration_date successfully. "
                    "input=%s, format=%s, parsed=%s",
                    license_expiration_date,
                    date_format,
                    expiry_date,
                )
                break
            except ValueError:
                continue

        if not expiry_date:
            logger.warning(
                "Step 2: invalid date format for license_expiration_date. input=%s",
                license_expiration_date,
            )
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Use YYYY-MM-DD, MM-DD-YYYY, or DD-MM-YYYY",
            )

        # Update Step 2 data
        contractor.state_license_number = state_license_number
        contractor.license_expiration_date = expiry_date
        contractor.license_status = license_status

        logger.info(
            "Step 2: updating contractor license info for user_id=%s | "
            "state_license_number=%s | license_expiration_date=%s | license_status=%s",
            current_user.id,
            state_license_number,
            expiry_date,
            license_status,
        )

        # Update registration step
        if contractor.registration_step < 2:
            contractor.registration_step = 2

        db.add(contractor)
        db.commit()
        db.refresh(contractor)

        logger.info(
            "Step 2 completed successfully for contractor id=%s, user_id=%s",
            contractor.id,
            current_user.id,
        )

        return {
            "message": "License information saved successfully",
            "step_completed": 2,
            "total_steps": 4,
            "is_completed": False,
            "next_step": 3,
        }

    except HTTPException as http_exc:
        # Log all 4xx validation/permission errors with context
        logger.warning(
            "Step 2 HTTPException for user_id=%s, email=%s: status=%s, detail=%s",
            getattr(current_user, "id", None),
            getattr(current_user, "email", None),
            http_exc.status_code,
            http_exc.detail,
        )
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
        f"Step 3 data received: trade_categories={getattr(data, 'trade_categories', None)}, trade_specialities={getattr(data, 'trade_specialities', None)}"
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

        # Update Step 3 data dynamically
        for field_name, field_value in data.model_dump().items():
            if hasattr(contractor, field_name):
                # For trade_specialities we accept a list; the Contractor model
                # uses an ARRAY(String) column so we can assign the list directly.
                if field_name == "trade_specialities" and isinstance(field_value, list):
                    setattr(contractor, field_name, field_value)
                else:
                    setattr(contractor, field_name, field_value)

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

        # Update Step 4 data - convert strings to arrays for database
        contractor.state = [data.state] if data.state else []
        contractor.country_city = [data.country_city] if data.country_city else []

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
