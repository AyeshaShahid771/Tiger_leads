import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.app import models, schemas
from src.app.api.deps import get_current_user
from src.app.core.database import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contractor", tags=["Contractor"])





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
        logger.warning(f"User {current_user.email} attempted contractor registration without Contractor role")
        raise HTTPException(
            status_code=403, 
            detail="You must set your role to 'Contractor' before registering as a contractor"
        )
    
    try:
        # Get existing contractor profile (create only here if missing)
        contractor = (
            db.query(models.user.Contractor)
            .filter(models.user.Contractor.user_id == current_user.id)
            .first()
        )

        if not contractor:
            logger.info(f"Creating new contractor profile for user_id: {current_user.id}")
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
        contractor.phone_number = data.phone_number
        contractor.email_address = data.email_address
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
            "next_step": 2
        }
        
    except Exception as e:
        logger.error(f"Error in contractor step 1 for user {current_user.id}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save business information")


@router.post("/step-2", response_model=schemas.ContractorStepResponse)
def contractor_step_2(
    data: schemas.ContractorStep2,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Step 2 of 4: License Information
    
    Requires authentication token in header.
    User must have completed Step 1.
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
            raise HTTPException(
                status_code=400, 
                detail="Please complete Step 1 first"
            )
        
        if contractor.registration_step < 1:
            raise HTTPException(
                status_code=400,
                detail="Please complete Step 1 before proceeding to Step 2"
            )
        
        # Update Step 2 data
        contractor.state_license_number = data.state_license_number
        contractor.county_license = data.county_license
        contractor.occupational_license = data.occupational_license
        contractor.license_picture_url = data.license_picture_url
        contractor.license_expiration_date = data.license_expiration_date
        contractor.license_status = data.license_status
        
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
            "next_step": 3
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in contractor step 2 for user {current_user.id}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save license information")


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
        
        if contractor.registration_step < 2:
            raise HTTPException(
                status_code=400,
                detail="Please complete Step 2 before proceeding to Step 3"
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
            "next_step": 4
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
                detail="Please complete Step 3 before proceeding to Step 4"
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
            "next_step": None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in contractor step 4 for user {current_user.id}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save service jurisdiction information")


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
            detail="Only users with Contractor role can access contractor profiles"
        )
    
    contractor = (
        db.query(models.user.Contractor)
        .filter(models.user.Contractor.user_id == current_user.id)
        .first()
    )
    
    if not contractor:
        raise HTTPException(
            status_code=404, 
            detail="Contractor profile not found. Please complete Step 1 to create your profile."
        )
    
    return contractor


@router.get("/registration-status")
def get_registration_status(
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the current registration status and progress.
    
    Requires authentication token in header.
    """
    logger.info(f"Registration status request from user: {current_user.email}")
    
    if current_user.role != "Contractor":
        return {
            "has_contractor_role": False,
            "message": "Please set your role to 'Contractor' first"
        }
    
    contractor = (
        db.query(models.user.Contractor)
        .filter(models.user.Contractor.user_id == current_user.id)
        .first()
    )
    
    if not contractor:
        return {
            "has_contractor_role": True,
            "profile_exists": False,
            "current_step": 0,
            "total_steps": 4,
            "is_completed": False,
            "next_step": 1,
            "message": "Please start by completing Step 1"
        }
    
    return {
        "has_contractor_role": True,
        "profile_exists": True,
        "current_step": contractor.registration_step,
        "total_steps": 4,
        "is_completed": contractor.is_completed,
        "next_step": contractor.registration_step + 1 if contractor.registration_step < 4 else None,
        "message": "Registration completed" if contractor.is_completed else f"Please complete Step {contractor.registration_step + 1}"
    }
