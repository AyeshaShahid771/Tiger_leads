from datetime import date
from typing import List, Optional

from pydantic import BaseModel, EmailStr, field_validator


# Step 1: Basic Business Information
class ContractorStep1(BaseModel):
    company_name: str
    primary_contact_name: str
    phone_number: str
    website_url: Optional[str] = None
    business_address: str
    business_type: str
    years_in_business: int

    class Config:
        json_schema_extra = {
            "example": {
                "company_name": "ACME Construction",
                "primary_contact_name": "John Doe",
                "phone_number": "(555) 234-3455",
                "website_url": "https://acmeconstruction.com",
                "business_address": "123 Main St., City, State",
                "business_type": "General Contractor",
                "years_in_business": 23,
            }
        }


# Step 2: License Information
class ContractorStep2(BaseModel):
    state_license_number: str
    county_license: str
    occupational_license: str
    license_picture_url: Optional[str] = None  # File upload URL
    license_expiration_date: date
    license_status: str = "Active"

    class Config:
        json_schema_extra = {
            "example": {
                "state_license_number": "342342343242243243",
                "county_license": "CTY-12345",
                "occupational_license": "OCC-67890",
                "license_picture_url": "/uploads/license_123.jpg",
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
    service_state: str
    service_zip_code: str

    class Config:
        json_schema_extra = {
            "example": {"service_state": "New York", "service_zip_code": "LS1 1UR"}
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
    phone_number: Optional[str] = None
    email_address: Optional[str] = None
    business_address: Optional[str] = None
    business_type: Optional[str] = None
    years_in_business: Optional[int] = None
    state_license_number: Optional[str] = None
    county_license: Optional[str] = None
    occupational_license: Optional[str] = None
    license_picture_url: Optional[str] = None
    license_expiration_date: Optional[date] = None
    license_status: Optional[str] = None
    work_type: Optional[str] = None
    business_types: Optional[str] = None  # JSON string
    service_state: Optional[str] = None
    service_zip_code: Optional[str] = None
    registration_step: int
    is_completed: bool

    class Config:
        from_attributes = True
