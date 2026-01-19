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
        .options(
            # Defer any potential large fields (none currently large binary in Supplier,
            # but keep pattern consistent)
        )
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

        # Update Step 2 data - convert to arrays for database
        supplier.service_states = data.service_states if data.service_states else []
        supplier.country_city = [data.country_city] if data.country_city else []

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
    state_license_number: str = Form(...),
    license_expiration_date: str = Form(...),
    license_status: str = Form("Active"),
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    license_picture: List[UploadFile] = File(default=[]),
    referrals: List[UploadFile] = File(default=[]),
    job_photos: List[UploadFile] = File(default=[]),
):
    """
    Step 3 of 4: Company Credentials

    Required form fields:
    - state_license_number: License number (string)
    - license_expiration_date: Expiration date (YYYY-MM-DD, MM-DD-YYYY, or DD-MM-YYYY)
    - license_status: License status (default: "Active")

    Optional file uploads (MULTIPLE FILES ALLOWED):
    - license_picture: License or certification images (JPG, PNG, PDF - max 20MB each)
    - referrals: Referrals documents (JPG, PNG, PDF - max 20MB each)
    - job_photos: Product gallery/job photos (JPG, PNG, PDF - max 20MB each)

    To upload multiple files in Swagger UI: Click the same file field multiple times to add more files.
    In Postman/curl: Use the same field name multiple times with different files.

    Requires authentication token in header.
    User must have completed Step 2.
    """
    logger.info(
        "Step 3 request from user: %s | state_license_number=%s | "
        "license_expiration_date=%s | license_status=%s",
        current_user.email,
        state_license_number,
        license_expiration_date,
        license_status,
    )

    # Verify user has supplier role
    if current_user.role != "Supplier":
        logger.warning(
            "Step 3: user %s attempted access without Supplier role (role=%s)",
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
                "Step 3: supplier profile not found for user_id=%s. "
                "User must complete Step 1 first.",
                current_user.id,
            )
            raise HTTPException(status_code=400, detail="Please complete Step 1 first")

        if supplier.registration_step < 2:
            logger.warning(
                "Step 3: user_id=%s has registration_step=%s. "
                "Step 2 must be completed before Step 3.",
                current_user.id,
                supplier.registration_step,
            )
            raise HTTPException(
                status_code=400,
                detail="Please complete Step 2 before proceeding to Step 3",
            )

        # File upload constants
        ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
        MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

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
            supplier.license_picture = license_data
            logger.info(f"Step 3: Assigned {len(license_data)} license_picture files to supplier")
        else:
            logger.info("Step 3: No license_picture files to assign")

        # Normalize and process referrals
        referrals_list = normalize_files(referrals)
        referrals_data = await process_multiple_files(referrals_list, "Referrals")
        if referrals_data:
            supplier.referrals = referrals_data
            logger.info(f"Step 3: Assigned {len(referrals_data)} referrals files to supplier")
        else:
            logger.info("Step 3: No referrals files to assign")

        # Normalize and process job photos
        job_photos_list = normalize_files(job_photos)
        job_photos_data = await process_multiple_files(job_photos_list, "Product gallery")
        if job_photos_data:
            supplier.job_photos = job_photos_data
            logger.info(f"Step 3: Assigned {len(job_photos_data)} job_photos files to supplier")
        else:
            logger.info("Step 3: No job_photos files to assign")

        # Parse date - try multiple formats
        expiry_date = None
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

        # Update Step 3 data
        supplier.state_license_number = state_license_number
        supplier.license_expiration_date = expiry_date
        supplier.license_status = license_status

        logger.info(
            "Step 3: updating supplier license info for user_id=%s | "
            "state_license_number=%s | license_expiration_date=%s | license_status=%s",
            current_user.id,
            state_license_number,
            expiry_date,
            license_status,
        )

        # DEBUG: Log what we're about to save
        logger.info(f"DEBUG Step 3: About to save - license_picture type: {type(supplier.license_picture)}, has {len(supplier.license_picture) if supplier.license_picture else 0} items")
        logger.info(f"DEBUG Step 3: About to save - referrals type: {type(supplier.referrals)}, has {len(supplier.referrals) if supplier.referrals else 0} items")
        logger.info(f"DEBUG Step 3: About to save - job_photos type: {type(supplier.job_photos)}, has {len(supplier.job_photos) if supplier.job_photos else 0} items")

        # Update registration step
        if supplier.registration_step < 3:
            supplier.registration_step = 3

        db.add(supplier)
        db.commit()
        db.refresh(supplier)

        # DEBUG: Log what was actually saved
        logger.info(f"DEBUG Step 3: After commit - license_picture: {supplier.license_picture}")
        logger.info(f"DEBUG Step 3: After commit - referrals: {supplier.referrals}")
        logger.info(f"DEBUG Step 3: After commit - job_photos: {supplier.job_photos}")

        logger.info(
            "Step 3 completed successfully for supplier id=%s, user_id=%s",
            supplier.id,
            current_user.id,
        )

        return {
            "message": "Company credentials saved successfully",
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
        logger.error(f"Error in supplier step 3 for user {current_user.id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500, detail="Failed to save company credentials"
        )


@router.post("/step-4", response_model=schemas.SupplierStepResponse)
def supplier_step_4(
    data: schemas.SupplierStep4,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Step 4 of 4: User Type (Final Step)

    Requires authentication token in header.
    This is the final step of supplier registration.
    """
    logger.info(f"Supplier Step 4 (Final) request from user: {current_user.email}")

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

        if supplier.registration_step < 3:
            raise HTTPException(
                status_code=400,
                detail="Please complete Step 3 before proceeding to Step 4",
            )

        # Update Step 4 data
        supplier.user_type = data.user_type

        # Mark registration as completed
        supplier.registration_step = 4
        supplier.is_completed = True

        db.add(supplier)
        db.commit()
        db.refresh(supplier)

        logger.info(f"Supplier registration completed for id: {supplier.id}")

        return {
            "message": "Supplier registration completed successfully! Your profile is now active.",
            "step_completed": 4,
            "total_steps": 4,
            "is_completed": True,
            "next_step": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in supplier step 4 for user {current_user.id}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save user type")


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


@router.put("/account", response_model=schemas.SupplierAccount)
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
        "phone_number": supplier.phone_number,
        "business_address": supplier.business_address,
    }


@router.put("/business-details", response_model=schemas.SupplierBusinessDetails)
def update_business_details(
    data: schemas.SupplierBusinessDetailsUpdate,
    current_user: models.user.User = Depends(require_main_or_editor),
    db: Session = Depends(get_db),
):
    supplier = _get_supplier(current_user, db)

    if data.company_name is not None:
        supplier.company_name = data.company_name
    if data.phone_number is not None:
        supplier.phone_number = data.phone_number
    if data.business_address is not None:
        supplier.business_address = data.business_address

    db.add(supplier)
    db.commit()
    db.refresh(supplier)

    return {
        "company_name": supplier.company_name,
        "phone_number": supplier.phone_number,
        "business_address": supplier.business_address,
    }


@router.get("/delivery-info", response_model=schemas.SupplierDeliveryInfo)
def get_delivery_info(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    supplier = _get_supplier(effective_user, db)
    return {
        "service_states": supplier.service_states if supplier.service_states else [],
        "country_city": supplier.country_city if supplier.country_city else [],
    }


@router.put("/delivery-info", response_model=schemas.SupplierDeliveryInfo)
def update_delivery_info(
    data: schemas.SupplierDeliveryInfoUpdate,
    current_user: models.user.User = Depends(require_main_or_editor),
    db: Session = Depends(get_db),
):
    supplier = _get_supplier(current_user, db)

    if data.service_states is not None:
        supplier.service_states = data.service_states
    if data.country_city is not None:
        supplier.country_city = [data.country_city] if data.country_city else []

    db.add(supplier)
    db.commit()
    db.refresh(supplier)

    return {
        "service_states": supplier.service_states if supplier.service_states else [],
        "country_city": supplier.country_city if supplier.country_city else [],
    }


@router.get("/capabilities", response_model=schemas.SupplierCapabilities)
def get_capabilities(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    supplier = _get_supplier(effective_user, db)
    return {
        "carries_inventory": supplier.carries_inventory,
        "offers_custom_orders": supplier.offers_custom_orders,
        "minimum_order_amount": supplier.minimum_order_amount,
        "accepts_urgent_requests": supplier.accepts_urgent_requests,
        "offers_credit_accounts": supplier.offers_credit_accounts,
    }


@router.put("/capabilities", response_model=schemas.SupplierCapabilities)
def update_capabilities(
    data: schemas.SupplierCapabilitiesUpdate,
    current_user: models.user.User = Depends(require_main_or_editor),
    db: Session = Depends(get_db),
):
    supplier = _get_supplier(current_user, db)

    if data.carries_inventory is not None:
        supplier.carries_inventory = _normalize_yes_no(
            data.carries_inventory, "carries_inventory"
        )
    if data.offers_custom_orders is not None:
        supplier.offers_custom_orders = _normalize_yes_no(
            data.offers_custom_orders, "offers_custom_orders"
        )
    if data.minimum_order_amount is not None:
        supplier.minimum_order_amount = data.minimum_order_amount
    if data.accepts_urgent_requests is not None:
        supplier.accepts_urgent_requests = _normalize_yes_no(
            data.accepts_urgent_requests, "accepts_urgent_requests"
        )
    if data.offers_credit_accounts is not None:
        supplier.offers_credit_accounts = _normalize_yes_no(
            data.offers_credit_accounts, "offers_credit_accounts"
        )

    db.add(supplier)
    db.commit()
    db.refresh(supplier)

    return {
        "carries_inventory": supplier.carries_inventory,
        "offers_custom_orders": supplier.offers_custom_orders,
        "minimum_order_amount": supplier.minimum_order_amount,
        "accepts_urgent_requests": supplier.accepts_urgent_requests,
        "offers_credit_accounts": supplier.offers_credit_accounts,
    }


@router.get("/products", response_model=schemas.SupplierProducts)
def get_products(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    supplier = _get_supplier(effective_user, db)
    return {
        "product_categories": supplier.product_categories,
        "product_types": list(supplier.product_types) if supplier.product_types else [],
    }


@router.put("/products", response_model=schemas.SupplierProducts)
def update_products(
    data: schemas.SupplierProductsUpdate,
    current_user: models.user.User = Depends(require_main_or_editor),
    db: Session = Depends(get_db),
):
    supplier = _get_supplier(current_user, db)

    if data.product_categories is not None:
        supplier.product_categories = data.product_categories
    if data.product_types is not None:
        supplier.product_types = data.product_types

    db.add(supplier)
    db.commit()
    db.refresh(supplier)

    return {
        "product_categories": supplier.product_categories,
        "product_types": list(supplier.product_types) if supplier.product_types else [],
    }
