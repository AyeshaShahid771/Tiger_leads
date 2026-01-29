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
from src.app.utils.email import send_registration_completion_email

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
    Step 2 of 4: Service Jurisdictions

    Requires authentication token in header.
    User can select multiple states and cities.
    """
    logger.info(f"Step 2 request from user: {current_user.email}")
    logger.info(
        f"Step 2 data received: state={getattr(data, 'state', None)}, country_city={getattr(data, 'country_city', None)}"
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

        # Update Step 2 data - state and country_city are now arrays
        if data.state:
            contractor.state = data.state if isinstance(data.state, list) else [data.state]
        if data.country_city:
            contractor.country_city = data.country_city if isinstance(data.country_city, list) else [data.country_city]

        # Update registration step
        if contractor.registration_step < 2:
            contractor.registration_step = 2

        db.add(contractor)
        db.commit()
        db.refresh(contractor)

        logger.info(f"Step 2 completed for contractor id: {contractor.id}")

        return {
            "message": "Service jurisdictions saved successfully",
            "step_completed": 2,
            "total_steps": 4,
            "is_completed": False,
            "next_step": 3,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating contractor service jurisdictions for user {current_user.id}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update service jurisdictions")


# Helper function to get contractor profile
def _get_contractor(user: models.user.User, db: Session) -> models.user.Contractor:
    contractor = (
        db.query(models.user.Contractor)
        .filter(models.user.Contractor.user_id == user.id)
        .first()
    )
    if not contractor:
        raise HTTPException(status_code=404, detail="Contractor profile not found")
    return contractor


# Document Preview Endpoints
@router.get("/preview-documents")
def preview_contractor_documents(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Get the first page of all uploaded documents for all document types.
    
    Returns JSON with all document types: license_picture, referrals, and job_photos.
    Each document includes base64-encoded data ready for frontend display.
    """
    contractor = _get_contractor(effective_user, db)
    
    def process_documents(files_json, doc_type):
        """Helper to process a document type"""
        documents = []
        if files_json and isinstance(files_json, list):
            for index, file_data in enumerate(files_json):
                if not isinstance(file_data, dict):
                    continue
                    
                filename = file_data.get("filename", f"document_{index}")
                content_type = file_data.get("content_type", "application/octet-stream")
                base64_data = file_data.get("data", "")
                size = file_data.get("size", 0)
                
                if base64_data:
                    documents.append({
                        "index": index,
                        "filename": filename,
                        "content_type": content_type,
                        "size": size,
                        "data": base64_data,
                    })
        return documents
    
    # Process all document types
    license_pictures = process_documents(contractor.license_picture, "license_picture")
    referrals = process_documents(contractor.referrals, "referrals")
    job_photos = process_documents(contractor.job_photos, "job_photos")
    
    return {
        "license_picture": {
            "documents": license_pictures,
            "total": len(license_pictures)
        },
        "referrals": {
            "documents": referrals,
            "total": len(referrals)
        },
        "job_photos": {
            "documents": job_photos,
            "total": len(job_photos)
        },
        "total_documents": len(license_pictures) + len(referrals) + len(job_photos)
    }


@router.delete("/delete-document/{document_type}/{file_index}")
def delete_contractor_document(
    document_type: str,
    file_index: int,
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Delete a specific document by type and index.
    
    document_type: "license_picture", "referrals", or "job_photos"
    file_index: Index of the file to delete (0-based)
    
    Returns success message and updated document count.
    """
    contractor = _get_contractor(effective_user, db)
    
    # Get the appropriate file array
    if document_type == "license_picture":
        files_json = contractor.license_picture
    elif document_type == "referrals":
        files_json = contractor.referrals
    elif document_type == "job_photos":
        files_json = contractor.job_photos
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid document type. Use 'license_picture', 'referrals', or 'job_photos'"
        )
    
    # Validate files exist
    if not files_json or not isinstance(files_json, list):
        raise HTTPException(status_code=404, detail=f"No {document_type} files found")
    
    # Validate file index
    if file_index < 0 or file_index >= len(files_json):
        raise HTTPException(
            status_code=404,
            detail=f"File index {file_index} out of range. Available files: 0-{len(files_json)-1}"
        )
    
    # Get filename before deletion for response
    deleted_filename = files_json[file_index].get("filename", "unknown") if isinstance(files_json[file_index], dict) else "unknown"
    
    # Delete the file at the specified index
    files_json.pop(file_index)
    
    # Update the database
    if document_type == "license_picture":
        contractor.license_picture = files_json
    elif document_type == "referrals":
        contractor.referrals = files_json
    elif document_type == "job_photos":
        contractor.job_photos = files_json
    
    db.add(contractor)
    db.commit()
    db.refresh(contractor)
    
    logger.info(f"Deleted {document_type} file at index {file_index} for contractor {contractor.id}")
    
    return {
        "message": f"Successfully deleted {document_type} file",
        "deleted_filename": deleted_filename,
        "deleted_index": file_index,
        "remaining_files": len(files_json)
    }



@router.post("/step-3", response_model=schemas.ContractorStepResponse)
async def contractor_step_3(
    data: schemas.ContractorStep3,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Step 3 of 4: License Information (Text Only)

    Requires authentication token in header.
    User must have completed Step 2.
    
    Accepts JSON body with licenses array:
    {
        "licenses": [
            {
                "license_number": "CA-123456",
                "expiration_date": "2025-12-31",
                "status": "Active"
            }
        ]
    }
    
    Note: File uploads (license pictures, referrals, job photos) should be done separately 
    via PATCH /contractor/license-info endpoint in Settings.
    """
    logger.info(
        "Step 3 request from user: %s | licenses_count=%s",
        current_user.email,
        len(data.licenses) if data.licenses else 0,
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



        # Save licenses to existing JSON array columns
        if data.licenses:
            contractor.state_license_number = [lic.license_number for lic in data.licenses]
            contractor.license_expiration_date = [lic.expiration_date for lic in data.licenses]
            contractor.license_status = [lic.status for lic in data.licenses]
            logger.info(f"Step 3: Saved {len(data.licenses)} licenses to contractor")
        else:
            contractor.state_license_number = []
            contractor.license_expiration_date = []
            contractor.license_status = []
            logger.info("Step 3: No licenses provided, saved empty arrays")

        # Update registration step
        if contractor.registration_step < 3:
            contractor.registration_step = 3

        db.add(contractor)
        db.commit()
        db.refresh(contractor)

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
async def contractor_step_4(
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

        # Update Step 4 data - user_type is now an array
        if data.user_type:
            contractor.user_type = data.user_type if isinstance(data.user_type, list) else [data.user_type]


        # Mark registration as completed
        contractor.registration_step = 4
        contractor.is_completed = True

        db.add(contractor)
        db.commit()
        db.refresh(contractor)

        logger.info(f"Contractor registration completed for id: {contractor.id}")

        # Send registration completion email
        try:
            # Get frontend URL from environment or use default
            frontend_url = os.getenv("FRONTEND_URL", "https://tigerleads.ai")
            login_url = f"{frontend_url}/login"
            
            # Get user name (company name or primary contact name)
            user_name = contractor.company_name or contractor.primary_contact_name or current_user.email
            
            # Send email (await the async function)
            await send_registration_completion_email(
                recipient_email=current_user.email,
                user_name=user_name,
                role="Contractor",
                login_url=login_url
            )
            logger.info(f"Registration completion email sent to {current_user.email}")
        except Exception as email_error:
            # Log error but don't fail the registration
            logger.error(f"Failed to send registration completion email: {str(email_error)}")

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
    state_license_number: str = Form(None),  # JSON string: '["CA-123", "NV-456"]'
    license_expiration_date: str = Form(None),  # JSON string: '["2025-12-31", "2026-06-30"]'
    license_status: str = Form(None),  # JSON string: '["Active", "Pending"]'
    license_picture: List[UploadFile] = File(None),
    referrals: List[UploadFile] = File(None),
    job_photos: List[UploadFile] = File(None),
    current_user: models.user.User = Depends(require_main_or_editor),
    db: Session = Depends(get_db),
):
    """
    PATCH endpoint - updates license text fields and REPLACES files.
    
    License fields should be sent as JSON strings representing arrays:
    - state_license_number: '["CA-123", "NV-456"]'
    - license_expiration_date: '["2025-12-31", "2026-06-30"]'
    - license_status: '["Active", "Pending"]'
    
    Files are replaced, not appended. If you send new files, they will replace the existing ones.
    """
    import json
    
    contractor = _get_contractor(current_user, db)

    # Update license text fields if provided (as JSON arrays)
    if state_license_number is not None:
        try:
            contractor.state_license_number = json.loads(state_license_number)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="state_license_number must be a valid JSON array")
    
    if license_expiration_date is not None:
        try:
            contractor.license_expiration_date = json.loads(license_expiration_date)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="license_expiration_date must be a valid JSON array")
    
    if license_status is not None:
        try:
            contractor.license_status = json.loads(license_status)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="license_status must be a valid JSON array")

    # File upload constants
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

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
