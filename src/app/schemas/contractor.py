from datetime import date
from typing import List, Optional

from pydantic import BaseModel, EmailStr, field_validator


# Step 1: Basic Business Information
class ContractorStep1(BaseModel):
    company_name: str
    phone_number: str
    website_url: Optional[str] = None
    business_address: str
    business_type: str
    years_in_business: int

    class Config:
        json_schema_extra = {
            "example": {
                "company_name": "BuildPro Contractors",
                "phone_number": "+91 88555 22789",
                "business_address": "221 Riverside Road, Pune",
                "business_type": "Civil Engineering",
                "years_in_business": 12,
            }
        }


# Step 2: License Information
# Note: This schema is for documentation only.
# The actual endpoint accepts multipart/form-data with Form() fields.
class ContractorStep2(BaseModel):
    state_license_number: str
    license_expiration_date: date
    license_status: str = "Active"

    class Config:
        json_schema_extra = {
            "example": {
                "state_license_number": "LIC-98452",
                "license_expiration_date": "2026-12-31",
                "license_status": "Active",
            }
        }


# Step 3: Trade Information
class ContractorStep3(BaseModel):
    work_type: str  # Residential, Commercial, Industrial
    business_types: List[str]  # Max 5 selections

    @field_validator("business_types")
    @classmethod
    def validate_business_types(cls, v):
        if len(v) > 5:
            raise ValueError("You can select a maximum of 5 business types")
        if len(v) == 0:
            raise ValueError("Please select at least one business type")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "work_type": "Residential",
                "business_types": ["Plumbing", "Electrical", "Concrete", "Landscaping"],
            }
        }


# Step 4: Service Jurisdictions
class ContractorStep4(BaseModel):
    state: str
    country_city: str

    class Config:
        json_schema_extra = {
            "example": {"state": "New York", "country_city": "USA/New York"}
        }


# Response models
class ContractorStepResponse(BaseModel):
    message: str
    step_completed: int
    total_steps: int
    is_completed: bool
    next_step: Optional[int] = None

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Step 1 completed successfully",
                "step_completed": 1,
                "total_steps": 4,
                "is_completed": False,
                "next_step": 2,
            }
        }


class ContractorProfile(BaseModel):
    id: int
    user_id: int
    company_name: Optional[str] = None
    primary_contact_name: Optional[str] = None
    phone_number: Optional[str] = None
    website_url: Optional[str] = None
    business_address: Optional[str] = None
    business_type: Optional[str] = None
    years_in_business: Optional[int] = None
    state_license_number: Optional[str] = None
    license_expiration_date: Optional[date] = None
    license_status: Optional[str] = None
    work_type: Optional[str] = None
    business_types: Optional[str] = None  # JSON string
    state: Optional[str] = None
    country_city: Optional[str] = None
    registration_step: int
    is_completed: bool

    class Config:
        from_attributes = True
