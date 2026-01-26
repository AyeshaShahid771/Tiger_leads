import json
import logging
import os
import shutil
import base64
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Union

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session, defer

from src.app import models, schemas
from src.app.api.deps import get_current_user, get_effective_user, require_main_account, require_main_or_editor
from src.app.api.endpoints.auth import hash_password, verify_password
from src.app.core.database import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contractor", tags=["Contractor"])

# Allowed file extensions
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


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
def contractor_step_2(
    data: schemas.ContractorStep2,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Step 2 of 4: Trade Information

    Requires authentication token in header.
    User can select multiple user types.
    """
    logger.info(f"Step 2 request from user: {current_user.email}")
    logger.info(
        f"Step 2 data received: user_type={getattr(data, 'user_type', None)}"
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

        if contractor.registration_step < 1:
            raise HTTPException(
                status_code=400,
                detail="Please complete Step 1 before proceeding to Step 2",
            )

        # Update Step 2 data dynamically
        for field_name, field_value in data.model_dump().items():
            if hasattr(contractor, field_name):
                # For user_type we accept a list; the Contractor model
                # uses an ARRAY(String) column so we can assign the list directly.
                if field_name == "user_type" and isinstance(field_value, list):
                    setattr(contractor, field_name, field_value)
                else:
                    setattr(contractor, field_name, field_value)

        # Update registration step
        if contractor.registration_step < 2:
            contractor.registration_step = 2

        db.add(contractor)
        db.commit()
        db.refresh(contractor)

        logger.info(f"Step 2 completed for contractor id: {contractor.id}")

        return {
            "message": "Contractor type added successfully",
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
        raise HTTPException(status_code=500, detail="Failed to save contractor type")



@router.post("/step-3", response_model=schemas.ContractorStepResponse)
async def contractor_step_3(
    state_license_number: str = Form(None),
    license_expiration_date: str = Form(None),
    license_status: str = Form(None),
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    license_picture: List[UploadFile] = File(default=[]),
    referrals: List[UploadFile] = File(default=[]),
    job_photos: List[UploadFile] = File(default=[]),
):
    """
    Step 3 of 4: License Information

    Requires authentication token in header.
    User must have completed Step 2.
    All fields must be submitted as multipart/form-data:
    - state_license_number, license_expiration_date, license_status as text fields
    - license_picture as files (JPG, JPEG, PNG, PDF - max 10MB each) - OPTIONAL - MULTIPLE FILES ALLOWED
    - referrals as files (JPG, JPEG, PNG, PDF - max 10MB each) - OPTIONAL - MULTIPLE FILES ALLOWED
    - job_photos as files (JPG, JPEG, PNG, PDF - max 10MB each) - OPTIONAL - MULTIPLE FILES ALLOWED
    
    To upload multiple files in Postman: Use the same field name multiple times with different files.
    """
    logger.info(
        "Step 3 request from user: %s | state_license_number=%s | "
        "license_expiration_date=%s | license_status=%s",
        current_user.email,
        state_license_number,
        license_expiration_date,
        license_status,
    )

    # Verify user has contractor role
    if current_user.role != "Contractor":
        logger.warning(
            "Step 3: user %s attempted access without Contractor role (role=%s)",
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
                "Step 3: contractor profile not found for user_id=%s. "
                "User must complete Step 1 first.",
                current_user.id,
            )
            raise HTTPException(status_code=400, detail="Please complete Step 1 first")

        if contractor.registration_step < 2:
            logger.warning(
                "Step 3: user_id=%s has registration_step=%s. "
                "Step 2 must be completed before Step 3.",
                current_user.id,
                contractor.registration_step,
            )
            raise HTTPException(
                status_code=400,
                detail="Please complete Step 2 before proceeding to Step 3",
            )

        # Helper function to normalize file input to a list
        def normalize_files(files_input: List[UploadFile]):
            """Filter out None values and empty filenames from the file list"""
            logger.info(f"DEBUG normalize_files: received {len(files_input)} files")
            result = [f for f in files_input if f is not None and hasattr(f, 'filename') and f.filename]
            logger.info(f"DEBUG normalize_files: filtered to {len(result)} valid files")
            for i, f in enumerate(result):
                logger.info(f"DEBUG normalize_files: file {i+1}: {f.filename}")
            return result

        # Helper function to process multiple file uploads
        async def process_multiple_files(files: List[UploadFile], file_type: str):
            if not files:
                logger.info("Step 3: %s not provided or empty", file_type)
                return None

            processed_files = []
            for file in files:
                file_ext = Path(file.filename).suffix.lower()
                if file_ext not in ALLOWED_EXTENSIONS:
                    logger.warning(
                        "Step 3: invalid file type for %s. filename=%s, ext=%s",
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
                        "Step 3: %s file too large. filename=%s, size_bytes=%s",
                        file_type,
                        file.filename,
                        len(contents),
                    )
                    raise HTTPException(
                        status_code=400,
                        detail=f"{file_type} file '{file.filename}' too large. Maximum size: {MAX_FILE_SIZE / (1024*1024)}MB",
                    )

                # Determine content type
                content_type = file.content_type or "image/jpeg"

                logger.info(
                    "Step 3: %s received. filename=%s, size_bytes=%s, content_type=%s",
                    file_type,
                    file.filename,
                    len(contents),
                    content_type,
                )

                # Store file data as base64 encoded string in JSON
                processed_files.append({
                    "filename": file.filename,
                    "content_type": content_type,
                    "data": base64.b64encode(contents).decode('utf-8'),
                    "size": len(contents)
                })

            return processed_files if processed_files else None

        # Normalize and process license pictures
        license_picture_list = normalize_files(license_picture)
        license_data = await process_multiple_files(license_picture_list, "License picture")
        if license_data:
            contractor.license_picture = license_data
            logger.info(f"Step 3: Assigned {len(license_data)} license_picture files to contractor")
        else:
            logger.info("Step 3: No license_picture files to assign")

        # Normalize and process referrals
        referrals_list = normalize_files(referrals)
        referrals_data = await process_multiple_files(referrals_list, "Referrals")
        if referrals_data:
            contractor.referrals = referrals_data
            logger.info(f"Step 3: Assigned {len(referrals_data)} referrals files to contractor")
        else:
            logger.info("Step 3: No referrals files to assign")

        # Normalize and process job photos
        job_photos_list = normalize_files(job_photos)
        job_photos_data = await process_multiple_files(job_photos_list, "Job photos")
        if job_photos_data:
            contractor.job_photos = job_photos_data
            logger.info(f"Step 3: Assigned {len(job_photos_data)} job_photos files to contractor")
        else:
            logger.info("Step 3: No job_photos files to assign")

        # Parse date - try multiple formats (only if provided)
        expiry_date = None
        if license_expiration_date:
            for date_format in ["%Y-%m-%d", "%m-%d-%Y", "%d-%m-%Y"]:
                try:
                    expiry_date = datetime.strptime(
                        license_expiration_date, date_format
                    ).date()
                    logger.info(
                        "Step 3: parsed license_expiration_date successfully. "
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
                    "Step 3: invalid date format for license_expiration_date. input=%s",
                    license_expiration_date,
                )
                raise HTTPException(
                    status_code=400,
                    detail="Invalid date format. Use YYYY-MM-DD, MM-DD-YYYY, or DD-MM-YYYY",
                )

        # Update Step 3 data (only if provided)
        if state_license_number is not None:
            contractor.state_license_number = state_license_number
        if expiry_date is not None:
            contractor.license_expiration_date = expiry_date
        if license_status is not None:
            contractor.license_status = license_status

        logger.info(
            "Step 3: updating contractor license info for user_id=%s | "
            "state_license_number=%s | license_expiration_date=%s | license_status=%s",
            current_user.id,
            state_license_number,
            expiry_date,
            license_status,
        )
        
        # DEBUG: Log what we're about to save
        logger.info(f"DEBUG Step 3: About to save - license_picture type: {type(contractor.license_picture)}, has {len(contractor.license_picture) if contractor.license_picture else 0} items")
        logger.info(f"DEBUG Step 3: About to save - referrals type: {type(contractor.referrals)}, has {len(contractor.referrals) if contractor.referrals else 0} items")
        logger.info(f"DEBUG Step 3: About to save - job_photos type: {type(contractor.job_photos)}, has {len(contractor.job_photos) if contractor.job_photos else 0} items")

        # Update registration step
        if contractor.registration_step < 3:
            contractor.registration_step = 3

        db.add(contractor)
        db.commit()
        db.refresh(contractor)
        
        # DEBUG: Log what was actually saved
        logger.info(f"DEBUG Step 3: After commit - license_picture: {contractor.license_picture}")
        logger.info(f"DEBUG Step 3: After commit - referrals: {contractor.referrals}")
        logger.info(f"DEBUG Step 3: After commit - job_photos: {contractor.job_photos}")

        logger.info(
            "Step 3 completed successfully for contractor id=%s, user_id=%s",
            contractor.id,
            current_user.id,
        )

        return {
            "message": "License information saved successfully",
            "step_completed": 3,
            "total_steps": 4,
            "is_completed": False,
            "next_step": 4,
        }

    except HTTPException as http_exc:
        # Log all 4xx validation/permission errors with context
        logger.warning(
            "Step 3 HTTPException for user_id=%s, email=%s: status=%s, detail=%s",
            getattr(current_user, "id", None),
            getattr(current_user, "email", None),
            http_exc.status_code,
            http_exc.detail,
        )
        raise
    except Exception as e:
        logger.error(f"Error in contractor step 3 for user {current_user.id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500, detail="Failed to save license information"
        )



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

        # Update Step 4 data - split comma-separated strings into arrays
        contractor.state = [s.strip() for s in data.state.split(',')] if data.state else []
        contractor.country_city = [c.strip() for c in data.country_city.split(',')] if data.country_city else []


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

    # Helper function to extract filenames from JSON arrays
    def get_filenames_from_json(files_json):
        """Extract comma-separated filenames from file JSON array"""
        if not files_json:
            return None
        if not isinstance(files_json, list):
            return None
        filenames = [f.get("filename", "") for f in files_json if isinstance(f, dict) and f.get("filename")]
        return ", ".join(filenames) if filenames else None

    # Construct response with parsed file metadata
    return {
        "id": contractor.id,
        "user_id": contractor.user_id,
        "company_name": contractor.company_name,
        "primary_contact_name": contractor.primary_contact_name,
        "phone_number": contractor.phone_number,
        "website_url": contractor.website_url,
        "business_address": contractor.business_address,
        "business_website_url": contractor.business_website_url,
        "state_license_number": contractor.state_license_number,
        "license_picture_filename": get_filenames_from_json(contractor.license_picture),
        "referrals_filename": get_filenames_from_json(contractor.referrals),
        "job_photos_filename": get_filenames_from_json(contractor.job_photos),
        "license_expiration_date": contractor.license_expiration_date,
        "license_status": contractor.license_status,
        "user_type": contractor.user_type,
        "state": contractor.state,
        "country_city": contractor.country_city,
        "registration_step": contractor.registration_step,
        "is_completed": contractor.is_completed,
    }


def _require_contractor(current_user: models.user.User) -> None:
    # Allow access if the user is a Contractor or is a sub-account (has parent_user_id).
    # Sub-accounts will be treated as accessing via their main account.
    if current_user.role == "Contractor":
        return
    if getattr(current_user, "parent_user_id", None):
        return
    raise HTTPException(
        status_code=403,
        detail="Only users with Contractor role can access this",
    )


def _get_contractor(
    current_user: models.user.User, db: Session
) -> models.user.Contractor:
    # Determine which user id to lookup for the Contractor profile.
    # If caller is a main account with role Contractor, use their id.
    if current_user.role == "Contractor":
        lookup_user_id = current_user.id
    else:
        # Caller is not a Contractor — if they are a sub-account, ensure their parent
        # exists and has role 'Contractor'; otherwise deny access.
        parent_id = getattr(current_user, "parent_user_id", None)
        if not parent_id:
            raise HTTPException(
                status_code=403,
                detail="Only users with Contractor role can access this",
            )
        parent = db.query(models.User).filter(models.User.id == parent_id).first()
        if not parent or parent.role != "Contractor":
            raise HTTPException(
                status_code=403,
                detail="Only users with Contractor role can access this",
            )
        lookup_user_id = parent_id

    contractor = (
        db.query(models.user.Contractor)
        # NOTE: Removed defer() to load file data for license-info endpoint
        .filter(models.user.Contractor.user_id == lookup_user_id)
        .first()
    )
    if not contractor:
        raise HTTPException(
            status_code=404,
            detail="Contractor profile not found. Please complete Step 1 to create your profile.",
        )
    return contractor


@router.get("/account", response_model=schemas.ContractorAccount)
def get_contractor_account(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    # Return main account data when called by a sub-account
    contractor = _get_contractor(effective_user, db)
    return {
        "name": contractor.primary_contact_name,
        "email": effective_user.email,
    }


@router.patch("/account", response_model=schemas.ContractorAccount)
def update_contractor_account(
    data: schemas.ContractorAccountUpdate,
    current_user: models.user.User = Depends(require_main_or_editor),
    db: Session = Depends(get_db),
):
    # Only main account users may update account info
    contractor = _get_contractor(current_user, db)

    if data.name is not None:
        contractor.primary_contact_name = data.name

    if data.new_password:
        if not verify_password(data.current_password, current_user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        current_user.password_hash = hash_password(data.new_password)
        db.add(current_user)

    db.add(contractor)
    db.commit()
    db.refresh(contractor)

    return {
        "name": contractor.primary_contact_name,
        "email": current_user.email,
    }


@router.get("/business-details", response_model=schemas.ContractorBusinessDetails)
def get_contractor_business_details(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    contractor = _get_contractor(effective_user, db)
    return {
        "company_name": contractor.company_name,
        "phone_number": contractor.phone_number,
        "business_address": contractor.business_address,
        "business_website_url": contractor.business_website_url,
    }


@router.patch("/business-details", response_model=schemas.ContractorBusinessDetails)
def update_contractor_business_details(
    data: schemas.ContractorBusinessDetailsUpdate,
    current_user: models.user.User = Depends(require_main_or_editor),
    db: Session = Depends(get_db),
):
    """
    PATCH endpoint - only updates provided fields.
    All fields are optional.
    """
    contractor = _get_contractor(current_user, db)

    # Only update fields that are provided
    if data.company_name is not None:
        contractor.company_name = data.company_name
    if data.phone_number is not None:
        contractor.phone_number = data.phone_number
    if data.business_address is not None:
        contractor.business_address = data.business_address
    if data.business_website_url is not None:
        contractor.business_website_url = data.business_website_url

    db.add(contractor)
    db.commit()
    db.refresh(contractor)

    return {
        "company_name": contractor.company_name,
        "phone_number": contractor.phone_number,
        "business_address": contractor.business_address,
        "business_website_url": contractor.business_website_url,
    }


@router.get("/license-info", response_model=schemas.ContractorLicenseInfo)
def get_contractor_license_info(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Get license information including file metadata.
    Returns file metadata (filename, size) for uploaded files.
    """
    contractor = _get_contractor(effective_user, db)
    
    # DEBUG: Log what we got from database
    logger.info(f"DEBUG: license_picture type: {type(contractor.license_picture)}, value: {contractor.license_picture}")
    logger.info(f"DEBUG: referrals type: {type(contractor.referrals)}, value: {contractor.referrals}")
    logger.info(f"DEBUG: job_photos type: {type(contractor.job_photos)}, value: {contractor.job_photos}")
    
    # Convert file JSON to metadata
    def get_file_metadata(files_json):
        if not files_json:
            logger.info(f"DEBUG: files_json is None or empty")
            return []
        if not isinstance(files_json, list):
            logger.info(f"DEBUG: files_json is not a list, type: {type(files_json)}")
            return []
        logger.info(f"DEBUG: files_json has {len(files_json)} items")
        return [
            {
                "filename": f.get("filename", ""),
                "size": f.get("size", 0),
                "content_type": f.get("content_type", "")
            }
            for f in files_json
            if isinstance(f, dict)
        ]
    
    return {
        "state_license_number": contractor.state_license_number,
        "license_expiration_date": contractor.license_expiration_date,
        "license_status": contractor.license_status,
        "license_picture": get_file_metadata(contractor.license_picture),
        "referrals": get_file_metadata(contractor.referrals),
        "job_photos": get_file_metadata(contractor.job_photos),
    }


@router.patch("/license-info")
async def update_contractor_license_info(
    state_license_number: str = Form(None),
    license_expiration_date: str = Form(None),
    license_status: str = Form(None),
    license_picture: List[UploadFile] = File(None),
    referrals: List[UploadFile] = File(None),
    job_photos: List[UploadFile] = File(None),
    current_user: models.user.User = Depends(require_main_or_editor),
    db: Session = Depends(get_db),
):
    """
    PATCH endpoint - updates text fields and REPLACES files.
    Files are replaced, not appended. If you send new files, they will replace the existing ones.
    """
    contractor = _get_contractor(current_user, db)

    # Update text fields if provided
    if state_license_number is not None:
        contractor.state_license_number = state_license_number
    if license_expiration_date is not None:
        # Parse date
        from datetime import datetime
        for date_format in ["%Y-%m-%d", "%m-%d-%Y", "%d-%m-%Y"]:
            try:
                contractor.license_expiration_date = datetime.strptime(
                    license_expiration_date, date_format
                ).date()
                break
            except ValueError:
                continue
    if license_status is not None:
        contractor.license_status = license_status

    # Helper to replace files (not append)
    async def replace_files(new_files, file_type):
        """Replace existing files with new files. Returns empty list if no new files provided."""
        if not new_files or all(not f or not f.filename for f in new_files):
            return None  # Return None to indicate no update should be made
        
        result = []
        for file in new_files:
            if not file or not file.filename:
                continue
            
            file_ext = Path(file.filename).suffix.lower()
            if file_ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file type for {file_type}"
                )
            
            contents = await file.read()
            if len(contents) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"{file_type} file too large"
                )
            
            result.append({
                "filename": file.filename,
                "content_type": file.content_type or "image/jpeg",
                "data": base64.b64encode(contents).decode('utf-8'),
                "size": len(contents)
            })
        
        return result

    # Replace files (only if new files are provided)
    new_license_pictures = await replace_files(license_picture, "License picture")
    if new_license_pictures is not None:
        contractor.license_picture = new_license_pictures
    
    new_referrals = await replace_files(referrals, "Referrals")
    if new_referrals is not None:
        contractor.referrals = new_referrals
    
    new_job_photos = await replace_files(job_photos, "Job photos")
    if new_job_photos is not None:
        contractor.job_photos = new_job_photos

    db.add(contractor)
    db.commit()
    db.refresh(contractor)

    # Return file metadata
    def get_file_metadata(files_json):
        if not files_json:
            return []
        if not isinstance(files_json, list):
            return []
        return [
            {
                "filename": f.get("filename", ""),
                "size": f.get("size", 0),
                "content_type": f.get("content_type", "")
            }
            for f in files_json
            if isinstance(f, dict)
        ]

    return {
        "state_license_number": contractor.state_license_number,
        "license_expiration_date": contractor.license_expiration_date,
        "license_status": contractor.license_status,
        "license_picture": get_file_metadata(contractor.license_picture),
        "referrals": get_file_metadata(contractor.referrals),
        "job_photos": get_file_metadata(contractor.job_photos),
    }


@router.get("/trade-info", response_model=schemas.ContractorTradeInfo)
def get_contractor_trade_info(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    contractor = _get_contractor(effective_user, db)
    return {
        "user_type": contractor.user_type,
    }


@router.patch("/trade-info", response_model=schemas.ContractorTradeInfo)
def update_contractor_trade_info(
    data: schemas.ContractorTradeInfoUpdate,
    current_user: models.user.User = Depends(require_main_or_editor),
    db: Session = Depends(get_db),
):
    """
    PATCH endpoint - APPENDS new user types to existing array.
    Removes duplicates automatically.
    """
    contractor = _get_contractor(current_user, db)

    if data.user_type is not None:
        # Get existing user types
        existing_types = contractor.user_type or []
        
        # Append new types
        combined_types = existing_types + data.user_type
        
        # Remove duplicates while preserving order
        seen = set()
        unique_types = []
        for user_type in combined_types:
            if user_type not in seen:
                seen.add(user_type)
                unique_types.append(user_type)
        
        contractor.user_type = unique_types

    db.add(contractor)
    db.commit()
    db.refresh(contractor)

    return {
        "user_type": contractor.user_type,
    }


@router.get("/location-info", response_model=schemas.ContractorLocationInfo)
def get_contractor_location_info(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Get location information including pending jurisdiction requests.
    """
    contractor = _get_contractor(effective_user, db)
    
    # Get pending jurisdictions for this user
    pending_jurisdictions = db.query(models.user.PendingJurisdiction).filter(
        models.user.PendingJurisdiction.user_id == effective_user.id,
        models.user.PendingJurisdiction.user_type == "Contractor",
        models.user.PendingJurisdiction.status == "pending"
    ).all()
    
    pending_list = [
        {
            "id": pj.id,
            "jurisdiction_type": pj.jurisdiction_type,
            "jurisdiction_value": pj.jurisdiction_value,
            "status": pj.status,
            "created_at": pj.created_at.isoformat() if pj.created_at else None
        }
        for pj in pending_jurisdictions
    ]
    
    return {
        "state": contractor.state if contractor.state else [],
        "country_city": contractor.country_city if contractor.country_city else [],
        "pending_jurisdictions": pending_list if pending_list else None,
    }


@router.patch("/location-info", response_model=schemas.ContractorLocationInfo)
def update_contractor_location_info(
    data: schemas.ContractorLocationInfoUpdate,
    current_user: models.user.User = Depends(require_main_or_editor),
    db: Session = Depends(get_db),
):
    """
    PATCH endpoint - new states/cities create pending jurisdictions.
    Requires admin approval before being added to user profile.
    """
    contractor = _get_contractor(current_user, db)
    
    # Helper to create pending jurisdiction if new
    def create_pending_if_new(jurisdiction_type, jurisdiction_value, existing_list):
        if not jurisdiction_value:
            return
        
        # Check if already in user's active list
        if jurisdiction_value in (existing_list or []):
            logger.info(f"Jurisdiction {jurisdiction_value} already exists for user {current_user.id}")
            return
        
        # Check if already pending
        existing_pending = db.query(models.user.PendingJurisdiction).filter(
            models.user.PendingJurisdiction.user_id == current_user.id,
            models.user.PendingJurisdiction.jurisdiction_type == jurisdiction_type,
            models.user.PendingJurisdiction.jurisdiction_value == jurisdiction_value,
            models.user.PendingJurisdiction.status == "pending"
        ).first()
        
        if existing_pending:
            logger.info(f"Jurisdiction {jurisdiction_value} already pending for user {current_user.id}")
            return
        
        # Create new pending jurisdiction
        pending = models.user.PendingJurisdiction(
            user_id=current_user.id,
            user_type="Contractor",
            jurisdiction_type=jurisdiction_type,
            jurisdiction_value=jurisdiction_value,
            status="pending"
        )
        db.add(pending)
        logger.info(f"Created pending jurisdiction: {jurisdiction_type}={jurisdiction_value} for user {current_user.id}")
    
    # Process state
    if data.state is not None:
        create_pending_if_new("state", data.state, contractor.state)
    
    # Process country_city
    if data.country_city is not None:
        create_pending_if_new("country_city", data.country_city, contractor.country_city)
    
    db.commit()
    
    # Get updated pending jurisdictions
    pending_jurisdictions = db.query(models.user.PendingJurisdiction).filter(
        models.user.PendingJurisdiction.user_id == current_user.id,
        models.user.PendingJurisdiction.user_type == "Contractor",
        models.user.PendingJurisdiction.status == "pending"
    ).all()
    
    pending_list = [
        {
            "id": pj.id,
            "jurisdiction_type": pj.jurisdiction_type,
            "jurisdiction_value": pj.jurisdiction_value,
            "status": pj.status,
            "created_at": pj.created_at.isoformat() if pj.created_at else None
        }
        for pj in pending_jurisdictions
    ]
    
    return {
        "state": contractor.state if contractor.state else [],
        "country_city": contractor.country_city if contractor.country_city else [],
        "pending_jurisdictions": pending_list if pending_list else None,
    }
