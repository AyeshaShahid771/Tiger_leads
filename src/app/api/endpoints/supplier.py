import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.app import models, schemas
from src.app.api.deps import get_current_user
from src.app.core.database import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/supplier", tags=["Supplier"])


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
        supplier.years_in_business = data.years_in_business
        supplier.business_type = data.business_type

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

        # Update Step 2 data
        supplier.service_states = json.dumps(data.service_states)
        supplier.service_zipcode = data.service_zipcode
        supplier.onsite_delivery = data.onsite_delivery
        supplier.delivery_lead_time = data.delivery_lead_time

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
def supplier_step_3(
    data: schemas.SupplierStep3,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Step 3 of 4: Supplier Capabilities

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

        # Update Step 3 data
        supplier.carries_inventory = data.carries_inventory
        supplier.offers_custom_orders = data.offers_custom_orders
        supplier.minimum_order_amount = data.minimum_order_amount
        supplier.accepts_urgent_requests = data.accepts_urgent_requests
        supplier.offers_credit_accounts = data.offers_credit_accounts

        # Update registration step
        if supplier.registration_step < 3:
            supplier.registration_step = 3

        db.add(supplier)
        db.commit()
        db.refresh(supplier)

        logger.info(f"Step 3 completed for supplier id: {supplier.id}")

        return {
            "message": "Supplier capabilities saved successfully",
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
        raise HTTPException(
            status_code=500, detail="Failed to save capabilities information"
        )


@router.post("/step-4", response_model=schemas.SupplierStepResponse)
def supplier_step_4(
    data: schemas.SupplierStep4,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Step 4 of 4: Product Categories (Final Step)

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
        supplier.product_categories = json.dumps(data.product_categories)

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
        raise HTTPException(status_code=500, detail="Failed to save product categories")


@router.get("/profile", response_model=schemas.SupplierProfile)
def get_supplier_profile(
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the supplier profile for the authenticated user.

    Requires authentication token in header.
    """
    logger.info(f"Supplier profile request from user: {current_user.email}")

    # Verify user has supplier role
    if current_user.role != "Supplier":
        raise HTTPException(
            status_code=403,
            detail="Only users with Supplier role can access supplier profiles",
        )

    supplier = (
        db.query(models.user.Supplier)
        .filter(models.user.Supplier.user_id == current_user.id)
        .first()
    )

    if not supplier:
        raise HTTPException(
            status_code=404,
            detail="Supplier profile not found. Please complete Step 1 to create your profile.",
        )

    return supplier

