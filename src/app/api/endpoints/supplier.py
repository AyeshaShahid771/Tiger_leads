import base64
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session, defer
from src.app import models, schemas
from src.app.api.deps import (
    get_current_user,
    get_effective_user,
    require_main_account,
    require_main_or_editor,
)
from src.app.api.endpoints.auth import hash_password, verify_password
from src.app.core.database import get_db
from src.app.utils.email import (
    send_registration_completion_email,
    send_admin_new_registration_notification,
)

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
    # Sub-accounts (editors/viewers) always resolve via their parent account.
    # Check parent_user_id FIRST so that an invited editor whose role was set
    # to 'Supplier' doesn't accidentally look up their own (non-existent) profile.
    parent_id = getattr(current_user, "parent_user_id", None)
    if parent_id:
        parent = (
            db.query(models.user.User).filter(models.user.User.id == parent_id).first()
        )
        if not parent or parent.role != "Supplier":
            raise HTTPException(
                status_code=403, detail="Only users with Supplier role can access this"
            )
        lookup_user_id = parent_id
    elif current_user.role == "Supplier":
        lookup_user_id = current_user.id
    else:
        raise HTTPException(
            status_code=403, detail="Only users with Supplier role can access this"
        )

    supplier = (
        db.query(models.user.Supplier)
        # NOTE: Removed defer() to load file data for profile endpoint
        .filter(models.user.Supplier.user_id == lookup_user_id).first()
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
    current_user: models.user.User = Depends(require_main_or_editor),
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
    current_user: models.user.User = Depends(require_main_or_editor),
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

        # Track duplicates
        duplicates_removed = 0

        # Update Step 2 data - merge with existing arrays, preserving order
        if data.service_states:
            incoming_states = (
                data.service_states
                if isinstance(data.service_states, list)
                else [data.service_states]
            )
            existing_states = supplier.service_states or []
            combined_states = existing_states + incoming_states
            supplier.service_states = list(dict.fromkeys(combined_states))

        if data.country_city:
            incoming_cities = (
                data.country_city
                if isinstance(data.country_city, list)
                else [data.country_city]
            )
            existing_cities = supplier.country_city or []
            combined_cities = existing_cities + incoming_cities
            supplier.country_city = list(dict.fromkeys(combined_cities))

        # Update registration step
        if supplier.registration_step < 2:
            supplier.registration_step = 2

        db.add(supplier)
        db.commit()
        db.refresh(supplier)

        logger.info(f"Step 2 completed for supplier id: {supplier.id}")

        base_message = "Service area information saved successfully"
        if duplicates_removed > 0:
            base_message += f". {duplicates_removed} duplicate areas were ignored."

        return {
            "message": base_message,
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


@router.delete("/jurisdiction", response_model=schemas.DeleteSupplierJurisdictionResponse)
def delete_supplier_jurisdiction(
    data: schemas.DeleteSupplierJurisdictionRequest,
    current_user: models.user.User = Depends(require_main_or_editor),
    db: Session = Depends(get_db),
):
    """
    DELETE endpoint to remove one or multiple jurisdictions from supplier profile.
    
    Request Body:
    - jurisdiction_type: Either "service_states" or "country_city"
    - jurisdiction_values: Array of values to remove (e.g., ["California", "Texas"])
    
    Works for single or multiple values in the same request.
    """
    logger.info(
        f"Delete jurisdiction request from user: {current_user.email}, type={data.jurisdiction_type}, values={data.jurisdiction_values}"
    )

    # Verify user has supplier role
    if current_user.role != "Supplier":
        logger.error(f"User {current_user.email} does not have Supplier role")
        raise HTTPException(status_code=403, detail="Supplier role required")

    try:
        # Get supplier profile
        supplier = (
            db.query(models.user.Supplier)
            .filter(models.user.Supplier.user_id == current_user.id)
            .first()
        )

        if not supplier:
            raise HTTPException(status_code=404, detail="Supplier profile not found")

        removed = []
        not_found = []

        # Remove the jurisdiction values from the appropriate array
        if data.jurisdiction_type == "service_states":
            current_states = supplier.service_states or []
            for value in data.jurisdiction_values:
                if value in current_states:
                    removed.append(value)
                else:
                    not_found.append(value)
            
            # Update the service_states array by removing all values in removed list
            if removed:
                supplier.service_states = [s for s in current_states if s not in removed]
                logger.info(
                    f"Removed {len(removed)} state(s) from supplier {supplier.id}: {removed}"
                )

        elif data.jurisdiction_type == "country_city":
            current_cities = supplier.country_city or []
            for value in data.jurisdiction_values:
                if value in current_cities:
                    removed.append(value)
                else:
                    not_found.append(value)
            
            # Update the country_city array by removing all values in removed list
            if removed:
                supplier.country_city = [c for c in current_cities if c not in removed]
                logger.info(
                    f"Removed {len(removed)} city/cities from supplier {supplier.id}: {removed}"
                )

        # Commit changes if any were removed
        if removed:
            db.add(supplier)
            db.commit()
            db.refresh(supplier)

        # Build response message
        if removed and not_found:
            message = f"{len(removed)} jurisdiction(s) removed successfully, {len(not_found)} not found"
        elif removed:
            message = f"{len(removed)} jurisdiction(s) removed successfully"
        elif not_found:
            message = f"No jurisdictions removed, {len(not_found)} not found"
        else:
            message = "No jurisdictions to remove"

        return {
            "message": message,
            "jurisdiction_type": data.jurisdiction_type,
            "removed": removed,
            "not_found": not_found,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error deleting jurisdiction for user {current_user.id}: {str(e)}"
        )
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete jurisdiction")


@router.post("/step-3", response_model=schemas.SupplierStepResponse)
async def supplier_step_3(
    data: schemas.SupplierStep3,
    current_user: models.user.User = Depends(require_main_or_editor),
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

        # Track if we found duplicates
        duplicates_removed = 0

        # Save user_type - merge with existing, preserving order (DIRECTLY add, no pending)
        if data.user_type:
            incoming_types = (
                data.user_type if isinstance(data.user_type, list) else [data.user_type]
            )
            existing_types = supplier.user_type or []
            combined_types = existing_types + incoming_types
            unique_types = list(dict.fromkeys(combined_types))
            duplicates_removed += len(combined_types) - len(unique_types)
            supplier.user_type = unique_types
            logger.info(f"Step 3: Saved user_type to supplier: {supplier.user_type}")
        else:
            supplier.user_type = []
            logger.info("Step 3: No user_type provided, saved empty array")

        # Update registration step
        if supplier.registration_step < 3:
            supplier.registration_step = 3

        db.add(supplier)
        db.commit()
        db.refresh(supplier)

        logger.info(f"Step 3 completed for supplier id: {supplier.id}")

        base_message = "User type information saved successfully"
        if duplicates_removed > 0:
            base_message += f". {duplicates_removed} duplicate categories were ignored."

        return {
            "message": base_message,
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
    current_user: models.user.User = Depends(require_main_or_editor),
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
            supplier.state_license_number = [
                lic.license_number for lic in data.licenses
            ]
            supplier.license_expiration_date = [
                lic.expiration_date for lic in data.licenses
            ]
            supplier.license_status = [lic.status for lic in data.licenses]
            logger.info(f"Step 4: Saved {len(data.licenses)} licenses to supplier")
        else:
            supplier.state_license_number = []
            supplier.license_expiration_date = []
            supplier.license_status = []
            logger.info("Step 4: No licenses provided, saved empty arrays")

        # Mark step 4 as completed
        supplier.registration_step = 4
        # Don't mark is_completed yet - that happens on final submission in Step 5

        db.add(supplier)
        db.commit()
        db.refresh(supplier)

        logger.info(
            "Step 4 completed successfully for supplier id=%s, user_id=%s",
            supplier.id,
            current_user.id,
        )

        return {
            "message": "Step 4 completed successfully! Please review and submit.",
            "step_completed": 4,
            "total_steps": 4,
            "is_completed": False,
            "next_step": 5,
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


@router.post("/submit-registration")
async def submit_supplier_registration(
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Final submission endpoint for Step 5 (Review & Submit).
    Marks registration as complete and sends the registration email ONCE.
    """
    logger.info(f"Final registration submission from supplier: {current_user.email}")

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
            raise HTTPException(status_code=400, detail="Supplier profile not found")

        if supplier.registration_step < 4:
            raise HTTPException(
                status_code=400,
                detail="Please complete all steps before final submission",
            )

        # Mark registration as completed
        supplier.is_completed = True

        # Send registration completion email ONLY if not already sent
        if not supplier.registration_email_sent:
            try:
                # Get frontend URL from environment or use default
                import os

                frontend_url = os.getenv("FRONTEND_URL", "https://tigerleads.ai")
                login_url = f"{frontend_url}/login"

                # Get user name (company name or primary contact name)
                user_name = (
                    supplier.company_name
                    or supplier.primary_contact_name
                    or current_user.email
                )

                # Send email to USER (await the async function)
                await send_registration_completion_email(
                    recipient_email=current_user.email,
                    user_name=user_name,
                    role="Supplier",
                    login_url=login_url,
                )

                # Send notification email to ADMIN
                admin_email = os.getenv("ADMIN_EMAIL", "admin@tigerleads.ai")
                dashboard_url = f"{frontend_url}/admin/dashboard"
                registration_date = datetime.utcnow().strftime("%B %d, %Y at %I:%M %p UTC")
                
                await send_admin_new_registration_notification(
                    admin_email=admin_email,
                    user_name=user_name,
                    user_email=current_user.email,
                    role="Supplier",
                    company_name=supplier.company_name or "N/A",
                    registration_date=registration_date,
                    dashboard_url=dashboard_url,
                )

                # Mark email as sent to prevent duplicates
                supplier.registration_email_sent = True
                logger.info(f"Registration completion email sent to USER: {current_user.email}")
                logger.info(f"Admin notification email sent to ADMIN: {admin_email}")
            except Exception as email_error:
                # Log error but don't fail the registration
                logger.error(
                    f"Failed to send registration completion email: {str(email_error)}"
                )
        else:
            logger.info(
                f"Registration email already sent for supplier {supplier.id}, skipping"
            )

        db.commit()
        db.refresh(supplier)

        return {
            "message": "Registration submitted successfully!",
            "is_completed": True,
            "email_sent": supplier.registration_email_sent,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error in final registration submission for user {current_user.id}: {str(e)}"
        )
        db.rollback()
        raise HTTPException(
            status_code=500, detail="Failed to submit registration"
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
        filenames = [
            f.get("filename", "")
            for f in files_json
            if isinstance(f, dict) and f.get("filename")
        ]
        return ", ".join(filenames) if filenames else None

    # Get approved user types
    approved_user_types = supplier.user_type if supplier.user_type else []

    # Get pending user types (awaiting admin approval)
    pending_user_types = (
        db.query(models.user.PendingUserType)
        .filter(
            models.user.PendingUserType.user_id == effective_user.id,
            models.user.PendingUserType.status == "pending",
        )
        .all()
    )
    pending_types = [p.user_type_value for p in pending_user_types]

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
        "user_type": approved_user_types,
        "user_type_pending": pending_types,  # Show pending categories awaiting approval
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
    # Return current logged-in user's data (not parent account)
    supplier = _get_supplier(effective_user, db)

    # If invitee, use their own name from the invitation record
    name = supplier.primary_contact_name
    if getattr(current_user, "parent_user_id", None):
        invitation = (
            db.query(models.user.UserInvitation)
            .filter(
                models.user.UserInvitation.invited_email == current_user.email.lower(),
                models.user.UserInvitation.status == "accepted",
            )
            .first()
        )
        if invitation and invitation.invited_name:
            name = invitation.invited_name

    return {
        "user_id": current_user.id,
        "name": name,
        "email": current_user.email,
    }


@router.patch("/account", response_model=schemas.SupplierAccount)
def update_supplier_account(
    data: schemas.SupplierAccountUpdate,
    current_user: models.user.User = Depends(require_main_account),
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
        "user_id": current_user.id,
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
                "content_type": f.get("content_type", ""),
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
    license_expiration_date: str = Form(
        None
    ),  # JSON string: '["2025-12-31", "2026-06-30"]'
    license_status: str = Form(None),  # JSON string: '["Active", "Pending"]'
    license_picture: List[UploadFile] = File(None),
    referrals: List[UploadFile] = File(None),
    job_photos: List[UploadFile] = File(None),
    current_user: models.user.User = Depends(require_main_account),
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
            raise HTTPException(
                status_code=400,
                detail="state_license_number must be a valid JSON array",
            )

    if license_expiration_date is not None:
        try:
            supplier.license_expiration_date = json.loads(license_expiration_date)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="license_expiration_date must be a valid JSON array",
            )

    if license_status is not None:
        try:
            supplier.license_status = json.loads(license_status)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400, detail="license_status must be a valid JSON array"
            )

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
                    status_code=400, detail=f"Invalid file type for {file_type}"
                )

            contents = await file.read()
            if len(contents) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400, detail=f"{file_type} file too large"
                )

            result.append(
                {
                    "filename": file.filename,
                    "content_type": file.content_type or "image/jpeg",
                    "data": base64.b64encode(contents).decode("utf-8"),
                    "size": len(contents),
                }
            )

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
                "content_type": f.get("content_type", ""),
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

    # Get pending and rejected jurisdictions for this user
    pending_jurisdictions = (
        db.query(models.user.PendingJurisdiction)
        .filter(
            models.user.PendingJurisdiction.user_id == effective_user.id,
            models.user.PendingJurisdiction.user_type == "Supplier",
            models.user.PendingJurisdiction.status.in_(["pending", "rejected"]),
        )
        .all()
    )

    pending_list = [
        {
            "id": pj.id,
            "jurisdiction_type": pj.jurisdiction_type,
            "jurisdiction_value": pj.jurisdiction_value,
            "status": pj.status,
            "rejection_note": pj.rejection_note,
            "created_at": pj.created_at.isoformat() if pj.created_at else None,
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
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    PATCH endpoint - new states/cities create pending jurisdictions.
    Requires admin approval before being added to user profile.
    """
    # Resolve the main account's supplier profile.
    # Editors operate on behalf of the account owner, so use effective_user.
    supplier = _get_supplier(effective_user, db)

    duplicates_ignored = [0]

    # Helper to create pending jurisdiction if new
    def create_pending_if_new(jurisdiction_type, jurisdiction_value, existing_list):
        if not jurisdiction_value:
            return

        # Check if already in user's active list
        if jurisdiction_value in (existing_list or []):
            logger.info(
                f"Jurisdiction {jurisdiction_value} already exists for user {effective_user.id}"
            )
            duplicates_ignored[0] += 1
            return

        # Check if already pending
        existing_pending = (
            db.query(models.user.PendingJurisdiction)
            .filter(
                models.user.PendingJurisdiction.user_id == effective_user.id,
                models.user.PendingJurisdiction.jurisdiction_type == jurisdiction_type,
                models.user.PendingJurisdiction.jurisdiction_value
                == jurisdiction_value,
                models.user.PendingJurisdiction.status == "pending",
            )
            .first()
        )

        if existing_pending:
            logger.info(
                f"Jurisdiction {jurisdiction_value} already pending for user {effective_user.id}"
            )
            duplicates_ignored[0] += 1
            return

        # Create new pending jurisdiction under the main account's user_id
        pending = models.user.PendingJurisdiction(
            user_id=effective_user.id,
            user_type="Supplier",
            jurisdiction_type=jurisdiction_type,
            jurisdiction_value=jurisdiction_value,
            status="pending",
        )
        db.add(pending)
        logger.info(
            f"Created pending jurisdiction: {jurisdiction_type}={jurisdiction_value} for user {effective_user.id}"
        )

    # Process state
    if data.state is not None:
        create_pending_if_new("state", data.state, supplier.service_states)

    # Process country_city
    if data.country_city is not None:
        create_pending_if_new("country_city", data.country_city, supplier.country_city)

    db.commit()

    # Get updated pending jurisdictions
    pending_jurisdictions = (
        db.query(models.user.PendingJurisdiction)
        .filter(
            models.user.PendingJurisdiction.user_id == effective_user.id,
            models.user.PendingJurisdiction.user_type == "Supplier",
            models.user.PendingJurisdiction.status == "pending",
        )
        .all()
    )

    pending_list = [
        {
            "id": pj.id,
            "jurisdiction_type": pj.jurisdiction_type,
            "jurisdiction_value": pj.jurisdiction_value,
            "status": pj.status,
            "created_at": pj.created_at.isoformat() if pj.created_at else None,
        }
        for pj in pending_jurisdictions
    ]

    base_message = "Location information updated successfully"
    if duplicates_ignored[0] > 0:
        base_message += (
            f". {duplicates_ignored[0]} duplicate jurisdiction requests were ignored."
        )

    return {
        "message": base_message,
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

    # Get pending and rejected user types
    pending_user_types = (
        db.query(models.user.PendingUserType)
        .filter(
            models.user.PendingUserType.user_id == effective_user.id,
            models.user.PendingUserType.status.in_(["pending", "rejected"]),
        )
        .all()
    )

    pending_list = [
        {
            "id": put.id,
            "user_role": put.user_role,
            "user_type_value": put.user_type_value,
            "status": put.status,
            "rejection_note": put.rejection_note,
            "created_at": put.created_at.isoformat() if put.created_at else None,
        }
        for put in pending_user_types
    ]

    return {
        "user_type": supplier.user_type if supplier.user_type else [],
        "pending_user_types": pending_list if pending_list else None,
    }


@router.patch("/user-type", response_model=schemas.SupplierUserType)
def update_supplier_user_type(
    data: schemas.SupplierUserTypeUpdate,
    current_user: models.user.User = Depends(require_main_or_editor),
    db: Session = Depends(get_db),
):
    """
    PATCH endpoint - Creates PENDING requests for NEW user types.
    Requires admin approval before being added to supplier profile.
    """
    supplier = _get_supplier(current_user, db)

    new_pending_count = 0
    duplicates_ignored = 0

    if data.user_type is not None:
        # Get existing approved user types
        existing_types = set(supplier.user_type or [])

        # Get existing pending user types to avoid duplicates
        existing_pending = (
            db.query(models.user.PendingUserType)
            .filter(
                models.user.PendingUserType.user_id == current_user.id,
                models.user.PendingUserType.status == "pending",
            )
            .all()
        )
        pending_values = set(p.user_type_value for p in existing_pending)

        for user_type in data.user_type:
            if user_type in existing_types or user_type in pending_values:
                duplicates_ignored += 1
                continue

            # Create new pending request for admin approval
            new_pending = models.user.PendingUserType(
                user_id=current_user.id,
                user_role="Supplier",
                user_type_value=user_type,
                status="pending",
            )
            db.add(new_pending)
            new_pending_count += 1

    db.commit()

    base_message = "User type update requested. "
    if new_pending_count > 0:
        base_message += (
            f"{new_pending_count} new categories are pending admin approval."
        )
    else:
        base_message += "No new categories were added."

    if duplicates_ignored > 0:
        base_message += (
            f" {duplicates_ignored} categories were already in your profile or pending."
        )

    return {
        "message": base_message,
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
                    documents.append(
                        {
                            "index": index,
                            "filename": filename,
                            "content_type": content_type,
                            "size": size,
                            "data": base64_data,
                        }
                    )
        return documents

    # Process all document types
    license_pictures = process_documents(supplier.license_picture, "license_picture")
    referrals = process_documents(supplier.referrals, "referrals")
    job_photos = process_documents(supplier.job_photos, "job_photos")

    return {
        "license_picture": {
            "documents": license_pictures,
            "total": len(license_pictures),
        },
        "referrals": {"documents": referrals, "total": len(referrals)},
        "job_photos": {"documents": job_photos, "total": len(job_photos)},
        "total_documents": len(license_pictures) + len(referrals) + len(job_photos),
    }


@router.delete("/delete-document/{document_type}/{file_index}")
def delete_supplier_document(
    document_type: str,
    file_index: int,
    current_user: models.user.User = Depends(require_main_or_editor),
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
            detail="Invalid document type. Use 'license_picture', 'referrals', or 'job_photos'",
        )

    # Validate files exist
    if not files_json or not isinstance(files_json, list):
        raise HTTPException(status_code=404, detail=f"No {document_type} files found")

    # Validate file index
    if file_index < 0 or file_index >= len(files_json):
        raise HTTPException(
            status_code=404,
            detail=f"File index {file_index} out of range. Available files: 0-{len(files_json)-1}",
        )

    # Get filename before deletion for response
    deleted_filename = (
        files_json[file_index].get("filename", "unknown")
        if isinstance(files_json[file_index], dict)
        else "unknown"
    )

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

    logger.info(
        f"Deleted {document_type} file at index {file_index} for supplier {supplier.id}"
    )

    return {
        "message": f"Successfully deleted {document_type} file",
        "deleted_filename": deleted_filename,
        "deleted_index": file_index,
        "remaining_files": len(files_json),
    }
