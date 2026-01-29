import json
import logging
import base64

from datetime import datetime
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pathlib import Path
from typing import Optional, List
from sqlalchemy.orm import Session, defer

from src.app import models, schemas
from src.app.api.deps import get_current_user, get_effective_user, require_main_account, require_main_or_editor
from src.app.api.endpoints.auth import hash_password, verify_password
from src.app.core.database import get_db
from src.app.utils.email import send_registration_completion_email

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/supplier", tags=["Supplier"])


def _require_supplier(current_user: models.user.User) -> None:
    # Allow access if the user is a Supplier or is a sub-account (has parent_user_id).
    if current_user.role == "Supplier":
        return
    if getattr(current_user, "parent_user_id", None):
        return
    raise HTTPException(
        status_code=403, detail="Only users with Supplier role can access this"
    )


def _get_supplier(current_user: models.user.User, db: Session) -> models.user.Supplier:
    # Determine which user id to lookup for the Supplier profile.
    # If caller is a main account with role Supplier, use their id.
    if current_user.role == "Supplier":
        lookup_user_id = current_user.id
    else:
        # Caller is not a Supplier — if they are a sub-account, ensure their parent
        # exists and has role 'Supplier'; otherwise deny access.
        parent_id = getattr(current_user, "parent_user_id", None)
        if not parent_id:
            raise HTTPException(
                status_code=403, detail="Only users with Supplier role can access this"
            )
        parent = (
            db.query(models.user.User).filter(models.user.User.id == parent_id).first()
        )
        if not parent or parent.role != "Supplier":
            raise HTTPException(
                status_code=403, detail="Only users with Supplier role can access this"
            )
        lookup_user_id = parent_id

    supplier = (
        db.query(models.user.Supplier)
        # NOTE: Removed defer() to load file data for profile endpoint
        .filter(models.user.Supplier.user_id == lookup_user_id)
        .first()
    )
    if not supplier:
        raise HTTPException(
            status_code=404,
            detail="Supplier profile not found. Please complete Step 1 to create your profile.",
        )
    return supplier


def _normalize_yes_no(value: str, field_name: str) -> str:
    normalized = value.lower()
    if normalized in ["yes", "true", "1"]:
        return "yes"
    if normalized in ["no", "false", "0"]:
        return "no"
    raise HTTPException(
        status_code=400,
        detail=f"{field_name} must be 'yes', 'no', 'true', or 'false'",
    )


@router.post("/step-1", response_model=schemas.SupplierStepResponse)
def supplier_step_1(
    data: schemas.SupplierStep1,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Step 1 of 4: Basic Business Information

    Requires authentication token in header.
    User must have role set to 'Supplier'.
    """
    logger.info(f"Supplier Step 1 request from user: {current_user.email}")

    # Verify user has supplier role
    if current_user.role != "Supplier":
        logger.warning(
            f"User {current_user.email} attempted supplier registration without Supplier role"
        )
        raise HTTPException(
            status_code=403,
            detail="You must set your role to 'Supplier' before registering as a supplier",
        )

    try:
        # Get existing supplier profile
        supplier = (
            db.query(models.user.Supplier)
            .filter(models.user.Supplier.user_id == current_user.id)
            .first()
        )

        if not supplier:
            logger.info(f"Creating new supplier profile for user_id: {current_user.id}")
            supplier = models.user.Supplier(
                user_id=current_user.id,
                registration_step=0,
                is_completed=False,
            )
            db.add(supplier)
            db.commit()
            db.refresh(supplier)
            logger.info(f"Supplier profile created with id: {supplier.id}")

        # Update Step 1 data
        supplier.company_name = data.company_name
        supplier.primary_contact_name = data.primary_contact_name
        supplier.phone_number = data.phone_number
        supplier.website_url = data.website_url
        supplier.business_address = data.business_address

        # Update registration step
        if supplier.registration_step < 1:
            supplier.registration_step = 1

        db.add(supplier)
        db.commit()
        db.refresh(supplier)

        logger.info(f"Step 1 completed for supplier id: {supplier.id}")

        return {
            "message": "Basic business information saved successfully",
            "step_completed": 1,
            "total_steps": 4,
            "is_completed": False,
            "next_step": 2,
        }

    except Exception as e:
        logger.error(f"Error in supplier step 1 for user {current_user.id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500, detail="Failed to save business information"
        )


@router.post("/step-2", response_model=schemas.SupplierStepResponse)
def supplier_step_2(
    data: schemas.SupplierStep2,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Step 2 of 4: Service Area / Delivery Radius

    Requires authentication token in header.
    User must have completed Step 1.
    """
    logger.info(f"Supplier Step 2 request from user: {current_user.email}")

    # Verify user has supplier role
    if current_user.role != "Supplier":
        raise HTTPException(status_code=403, detail="Supplier role required")

    try:
        # Get supplier profile
        supplier = (
            db.query(models.user.Supplier)
            .filter(models.user.Supplier.user_id == current_user.id)
            .first()
        )

        if not supplier:
            raise HTTPException(status_code=400, detail="Please complete Step 1 first")

        if supplier.registration_step < 1:
            raise HTTPException(
                status_code=400,
                detail="Please complete Step 1 before proceeding to Step 2",
            )

        # Update Step 2 data - both are arrays now
        supplier.service_states = data.service_states if data.service_states else []
        supplier.country_city = data.country_city if data.country_city else []

        # Update registration step
        if supplier.registration_step < 2:
            supplier.registration_step = 2

        db.add(supplier)
        db.commit()
        db.refresh(supplier)

        logger.info(f"Step 2 completed for supplier id: {supplier.id}")

        return {
            "message": "Service area information saved successfully",
            "step_completed": 2,
            "total_steps": 4,
            "is_completed": False,
            "next_step": 3,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in supplier step 2 for user {current_user.id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500, detail="Failed to save service area information"
        )


@router.post("/step-3", response_model=schemas.SupplierStepResponse)
async def supplier_step_3(
    data: schemas.SupplierStep3,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Step 3 of 4: User Type

    Requires authentication token in header.
    User must have completed Step 2.
    """
    logger.info(f"Supplier Step 3 request from user: {current_user.email}")

    # Verify user has supplier role
    if current_user.role != "Supplier":
        raise HTTPException(status_code=403, detail="Supplier role required")

    try:
        # Get supplier profile
        supplier = (
            db.query(models.user.Supplier)
            .filter(models.user.Supplier.user_id == current_user.id)
            .first()
        )

        if not supplier:
            raise HTTPException(status_code=400, detail="Please complete Step 1 first")

        if supplier.registration_step < 2:
            raise HTTPException(
                status_code=400,
                detail="Please complete Step 2 before proceeding to Step 3",
            )

        # Update Step 3 data - User Type
        supplier.user_type = data.user_type

        # Update registration step
        if supplier.registration_step < 3:
            supplier.registration_step = 3

        db.add(supplier)
        db.commit()
        db.refresh(supplier)

        logger.info(f"Step 3 completed for supplier id: {supplier.id}")

        return {
            "message": "User type saved successfully",
            "step_completed": 3,
            "total_steps": 4,
            "is_completed": False,
            "next_step": 4,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in supplier step 3 for user {current_user.id}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save user type")


@router.post("/step-4", response_model=schemas.SupplierStepResponse)
async def supplier_step_4(
    data: schemas.SupplierStep4,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Step 4 of 4: Company Credentials (Final Step)

    Requires authentication token in header.
    This is the final step of supplier registration.
    
    Accepts JSON body with licenses array:
    {
        "licenses": [
            {
                "license_number": "LIC-12345",
                "expiration_date": "2026-12-31",
                "status": "Active"
            }
        ]
    }
    
    Note: File uploads (license pictures, referrals, job photos) should be done separately 
    via PATCH /supplier/license-info endpoint in Settings.
    """
    logger.info(
        "Step 4 (Final) request from user: %s | licenses_count=%s",
        current_user.email,
        len(data.licenses) if data.licenses else 0,
    )

    # Verify user has supplier role
    if current_user.role != "Supplier":
        logger.warning(
            "Step 4: user %s attempted access without Supplier role (role=%s)",
            current_user.email,
            current_user.role,
        )
        raise HTTPException(status_code=403, detail="Supplier role required")

    try:
        # Get supplier profile
        supplier = (
            db.query(models.user.Supplier)
            .filter(models.user.Supplier.user_id == current_user.id)
            .first()
        )

        if not supplier:
            logger.warning(
                "Step 4: supplier profile not found for user_id=%s. "
                "User must complete Step 1 first.",
                current_user.id,
            )
            raise HTTPException(status_code=400, detail="Please complete Step 1 first")

        if supplier.registration_step < 3:
            logger.warning(
                "Step 4: user_id=%s has registration_step=%s. "
                "Step 3 must be completed before Step 4.",
                current_user.id,
                supplier.registration_step,
            )
            raise HTTPException(
                status_code=400,
                detail="Please complete Step 3 before proceeding to Step 4",
            )

        # Save licenses to existing JSON array columns
        if data.licenses:
            supplier.state_license_number = [lic.license_number for lic in data.licenses]
            supplier.license_expiration_date = [lic.expiration_date for lic in data.licenses]
            supplier.license_status = [lic.status for lic in data.licenses]
            logger.info(f"Step 4: Saved {len(data.licenses)} licenses to supplier")
        else:
            supplier.state_license_number = []
            supplier.license_expiration_date = []
            supplier.license_status = []
            logger.info("Step 4: No licenses provided, saved empty arrays")

        # Mark registration as completed
        supplier.registration_step = 4
        supplier.is_completed = True

        db.add(supplier)
        db.commit()
        db.refresh(supplier)

        logger.info(
            "Step 4 completed successfully for supplier id=%s, user_id=%s",
            supplier.id,
            current_user.id,
        )

        # Send registration completion email
        try:
            # Get frontend URL from environment or use default
            import os
            frontend_url = os.getenv("FRONTEND_URL", "https://tigerleads.ai")
            login_url = f"{frontend_url}/login"
            
            # Get user name (company name or primary contact name)
            user_name = supplier.company_name or supplier.primary_contact_name or current_user.email
            
            # Send email (await the async function)
            await send_registration_completion_email(
                recipient_email=current_user.email,
                user_name=user_name,
                role="Supplier",
                login_url=login_url
            )
            logger.info(f"Registration completion email sent to {current_user.email}")
        except Exception as email_error:
            # Log error but don't fail the registration
            logger.error(f"Failed to send registration completion email: {str(email_error)}")

        return {
            "message": "Supplier registration completed successfully! Your profile is now active.",
            "step_completed": 4,
            "total_steps": 4,
            "is_completed": True,
            "next_step": None,
        }

    except HTTPException as http_exc:
        # Log all 4xx validation/permission errors with context
        logger.warning(
            "Step 4 HTTPException for user_id=%s, email=%s: status=%s, detail=%s",
            getattr(current_user, "id", None),
            getattr(current_user, "email", None),
            http_exc.status_code,
            http_exc.detail,
        )
        raise
    except Exception as e:
        logger.error(f"Error in supplier step 4 for user {current_user.id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500, detail="Failed to save company credentials"
        )


@router.get("/profile", response_model=schemas.SupplierProfile)
def get_supplier_profile(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """Get the supplier profile for the authenticated user or their main account."""
    logger.info(f"Supplier profile request from user: {current_user.email}")

    supplier = _get_supplier(effective_user, db)

    # Helper function to extract filenames from JSON arrays
    def get_filenames_from_json(files_json):
        """Extract comma-separated filenames from file JSON array"""
        if not files_json:
            return None
        if not isinstance(files_json, list):
            return None
        filenames = [f.get("filename", "") for f in files_json if isinstance(f, dict) and f.get("filename")]
        return ", ".join(filenames) if filenames else None

    # Return all supplier profile data
    supplier_dict = {
        "id": supplier.id,
        "user_id": supplier.user_id,
        # Step 1 fields
        "company_name": supplier.company_name,
        "primary_contact_name": supplier.primary_contact_name,
        "phone_number": supplier.phone_number,
        "website_url": supplier.website_url,
        "business_address": supplier.business_address,
        # Step 2 fields
        "service_states": supplier.service_states if supplier.service_states else [],
        "country_city": supplier.country_city if supplier.country_city else [],
        # Step 3 fields
        "state_license_number": supplier.state_license_number,
        "license_expiration_date": supplier.license_expiration_date,
        "license_status": supplier.license_status,
        "license_picture_filename": get_filenames_from_json(supplier.license_picture),
        "referrals_filename": get_filenames_from_json(supplier.referrals),
        "job_photos_filename": get_filenames_from_json(supplier.job_photos),
        # Step 4 fields
        "user_type": supplier.user_type if supplier.user_type else [],
        # Tracking fields
        "registration_step": supplier.registration_step,
        "is_completed": supplier.is_completed,
    }

    return supplier_dict


@router.get("/account", response_model=schemas.SupplierAccount)
def get_supplier_account(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    supplier = _get_supplier(effective_user, db)
    return {
        "name": supplier.primary_contact_name,
        "email": effective_user.email,
    }


@router.patch("/account", response_model=schemas.SupplierAccount)
def update_supplier_account(
    data: schemas.SupplierAccountUpdate,
    current_user: models.user.User = Depends(require_main_or_editor),
    db: Session = Depends(get_db),
):
    supplier = _get_supplier(current_user, db)

    if data.name is not None:
        supplier.primary_contact_name = data.name

    if data.new_password:
        if not verify_password(data.current_password, current_user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        current_user.password_hash = hash_password(data.new_password)
        db.add(current_user)

    db.add(supplier)
    db.commit()
    db.refresh(supplier)

    return {
        "name": supplier.primary_contact_name,
        "email": current_user.email,
    }


@router.get("/business-details", response_model=schemas.SupplierBusinessDetails)
def get_business_details(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    supplier = _get_supplier(effective_user, db)
    return {
        "company_name": supplier.company_name,
        "primary_contact_name": supplier.primary_contact_name,
        "phone_number": supplier.phone_number,
        "website_url": supplier.website_url,
        "business_address": supplier.business_address,
    }


@router.patch("/business-details", response_model=schemas.SupplierBusinessDetails)
def update_business_details(
    data: schemas.SupplierBusinessDetailsUpdate,
    current_user: models.user.User = Depends(require_main_or_editor),
    db: Session = Depends(get_db),
):
    """
    PATCH endpoint - only updates provided fields.
    All fields are optional.
    """
    supplier = _get_supplier(current_user, db)

    if data.company_name is not None:
        supplier.company_name = data.company_name
    if data.primary_contact_name is not None:
        supplier.primary_contact_name = data.primary_contact_name
    if data.phone_number is not None:
        supplier.phone_number = data.phone_number
    if data.website_url is not None:
        supplier.website_url = data.website_url
    if data.business_address is not None:
        supplier.business_address = data.business_address

    db.add(supplier)
    db.commit()
    db.refresh(supplier)

    return {
        "company_name": supplier.company_name,
        "primary_contact_name": supplier.primary_contact_name,
        "phone_number": supplier.phone_number,
        "website_url": supplier.website_url,
        "business_address": supplier.business_address,
    }


@router.get("/license-info", response_model=schemas.SupplierLicenseInfo)
def get_supplier_license_info(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Get license information including file metadata.
    Returns file metadata (filename, size) for uploaded files.
    """
    supplier = _get_supplier(effective_user, db)
    
    # Convert file JSON to metadata
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
        "state_license_number": supplier.state_license_number,
        "license_expiration_date": supplier.license_expiration_date,
        "license_status": supplier.license_status,
        "license_picture": get_file_metadata(supplier.license_picture),
        "referrals": get_file_metadata(supplier.referrals),
        "job_photos": get_file_metadata(supplier.job_photos),
    }


@router.patch("/license-info")
async def update_supplier_license_info(
    state_license_number: str = Form(None),  # JSON string: '["LIC-123", "LIC-456"]'
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
    - state_license_number: '["LIC-123", "LIC-456"]'
    - license_expiration_date: '["2025-12-31", "2026-06-30"]'
    - license_status: '["Active", "Pending"]'
    
    Files are replaced, not appended. If you send new files, they will replace the existing ones.
    """
    import json
    
    supplier = _get_supplier(current_user, db)

    # Update license text fields if provided (as JSON arrays)
    if state_license_number is not None:
        try:
            supplier.state_license_number = json.loads(state_license_number)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="state_license_number must be a valid JSON array")
    
    if license_expiration_date is not None:
        try:
            supplier.license_expiration_date = json.loads(license_expiration_date)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="license_expiration_date must be a valid JSON array")
    
    if license_status is not None:
        try:
            supplier.license_status = json.loads(license_status)
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
        supplier.license_picture = new_license_pictures
    
    new_referrals = await replace_files(referrals, "Referrals")
    if new_referrals is not None:
        supplier.referrals = new_referrals
    
    new_job_photos = await replace_files(job_photos, "Job photos")
    if new_job_photos is not None:
        supplier.job_photos = new_job_photos

    db.add(supplier)
    db.commit()
    db.refresh(supplier)

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
        "state_license_number": supplier.state_license_number,
        "license_expiration_date": supplier.license_expiration_date,
        "license_status": supplier.license_status,
        "license_picture": get_file_metadata(supplier.license_picture),
        "referrals": get_file_metadata(supplier.referrals),
        "job_photos": get_file_metadata(supplier.job_photos),
    }


@router.get("/location-info", response_model=schemas.SupplierLocationInfo)
def get_location_info(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Get location information including pending jurisdiction requests.
    """
    supplier = _get_supplier(effective_user, db)
    
    # Get pending jurisdictions for this user
    pending_jurisdictions = db.query(models.user.PendingJurisdiction).filter(
        models.user.PendingJurisdiction.user_id == effective_user.id,
        models.user.PendingJurisdiction.user_type == "Supplier",
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
        "service_states": supplier.service_states if supplier.service_states else [],
        "country_city": supplier.country_city if supplier.country_city else [],
        "pending_jurisdictions": pending_list if pending_list else None,
    }


@router.patch("/location-info", response_model=schemas.SupplierLocationInfo)
def update_location_info(
    data: schemas.SupplierLocationInfoUpdate,
    current_user: models.user.User = Depends(require_main_or_editor),
    db: Session = Depends(get_db),
):
    """
    PATCH endpoint - new states/cities create pending jurisdictions.
    Requires admin approval before being added to user profile.
    """
    supplier = _get_supplier(current_user, db)
    
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
            user_type="Supplier",
            jurisdiction_type=jurisdiction_type,
            jurisdiction_value=jurisdiction_value,
            status="pending"
        )
        db.add(pending)
        logger.info(f"Created pending jurisdiction: {jurisdiction_type}={jurisdiction_value} for user {current_user.id}")
    
    # Process state
    if data.state is not None:
        create_pending_if_new("state", data.state, supplier.service_states)
    
    # Process country_city
    if data.country_city is not None:
        create_pending_if_new("country_city", data.country_city, supplier.country_city)
    
    db.commit()
    
    # Get updated pending jurisdictions
    pending_jurisdictions = db.query(models.user.PendingJurisdiction).filter(
        models.user.PendingJurisdiction.user_id == current_user.id,
        models.user.PendingJurisdiction.user_type == "Supplier",
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
        "service_states": supplier.service_states if supplier.service_states else [],
        "country_city": supplier.country_city if supplier.country_city else [],
        "pending_jurisdictions": pending_list if pending_list else None,
    }



@router.get("/user-type", response_model=schemas.SupplierUserType)
def get_supplier_user_type(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    supplier = _get_supplier(effective_user, db)
    return {
        "user_type": supplier.user_type if supplier.user_type else [],
    }


@router.patch("/user-type", response_model=schemas.SupplierUserType)
def update_supplier_user_type(
    data: schemas.SupplierUserTypeUpdate,
    current_user: models.user.User = Depends(require_main_or_editor),
    db: Session = Depends(get_db),
):
    """
    PATCH endpoint - APPENDS new user types to existing array.
    Removes duplicates automatically.
    """
    supplier = _get_supplier(current_user, db)

    if data.user_type is not None:
        # Get existing user types
        existing_types = supplier.user_type or []
        
        # Append new types
        combined_types = existing_types + data.user_type
        
        # Remove duplicates while preserving order
        seen = set()
        unique_types = []
        for user_type in combined_types:
            if user_type not in seen:
                seen.add(user_type)
                unique_types.append(user_type)
        
        supplier.user_type = unique_types

    db.add(supplier)
    db.commit()
    db.refresh(supplier)

    return {
        "user_type": supplier.user_type if supplier.user_type else [],
    }


@router.get("/user-type", response_model=schemas.SupplierUserType)
def get_supplier_user_type(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    supplier = _get_supplier(effective_user, db)
    return {
        "user_type": supplier.user_type if supplier.user_type else [],
    }


@router.patch("/user-type", response_model=schemas.SupplierUserType)
def update_supplier_user_type(
    data: schemas.SupplierUserTypeUpdate,
    current_user: models.user.User = Depends(require_main_or_editor),
    db: Session = Depends(get_db),
):
    """
    PATCH endpoint - APPENDS new user types to existing array.
    Removes duplicates automatically.
    """
    supplier = _get_supplier(current_user, db)

    if data.user_type is not None:
        # Get existing user types
        existing_types = supplier.user_type or []
        
        # Append new types
        combined_types = existing_types + data.user_type
        
        # Remove duplicates while preserving order
        seen = set()
        unique_types = []
        for user_type in combined_types:
            if user_type not in seen:
                seen.add(user_type)
                unique_types.append(user_type)
        
        supplier.user_type = unique_types

    db.add(supplier)
    db.commit()
    db.refresh(supplier)

    return {
        "user_type": supplier.user_type if supplier.user_type else [],
    }


# Document Preview Endpoints
@router.get("/preview-documents")
def preview_supplier_documents(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Get the first page of all uploaded documents for all document types.
    
    Returns JSON with all document types: license_picture, referrals, and job_photos.
    Each document includes base64-encoded data ready for frontend display.
    """
    supplier = _get_supplier(effective_user, db)
    
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
    license_pictures = process_documents(supplier.license_picture, "license_picture")
    referrals = process_documents(supplier.referrals, "referrals")
    job_photos = process_documents(supplier.job_photos, "job_photos")
    
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
def delete_supplier_document(
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
    supplier = _get_supplier(effective_user, db)
    
    # Get the appropriate file array
    if document_type == "license_picture":
        files_json = supplier.license_picture
    elif document_type == "referrals":
        files_json = supplier.referrals
    elif document_type == "job_photos":
        files_json = supplier.job_photos
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
        supplier.license_picture = files_json
    elif document_type == "referrals":
        supplier.referrals = files_json
    elif document_type == "job_photos":
        supplier.job_photos = files_json
    
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    
    logger.info(f"Deleted {document_type} file at index {file_index} for supplier {supplier.id}")
    
    return {
        "message": f"Successfully deleted {document_type} file",
        "deleted_filename": deleted_filename,
        "deleted_index": file_index,
        "remaining_files": len(files_json)
    }
