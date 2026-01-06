from datetime import date
from typing import List, Optional

from pydantic import BaseModel, EmailStr, field_validator, model_validator


# Step 1: Basic Business Information
class ContractorStep1(BaseModel):
    company_name: str
    phone_number: str
    business_address: str
    business_website_url: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "company_name": "BuildPro Contractors",
                "phone_number": "+91 88555 22789",
                "business_address": "221 Riverside Road, Pune",
                "business_website_url": "https://www.buildprocontractors.com",
            }
        }


# Step 2: License Information
# Note: This schema is for documentation only.
# The actual endpoint accepts multipart/form-data with Form() fields and File() uploads.
class ContractorStep2(BaseModel):
    state_license_number: str
    license_expiration_date: date
    license_status: str = "Active"
    # Optional file uploads (not shown in schema as they're File() not Form()):
    # - license_picture (JPG, PNG, PDF)
    # - referrals (JPG, PNG, PDF)
    # - job_photos (JPG, PNG, PDF)

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
    user_type: List[str]  # Array of user types

    @field_validator("user_type")
    @classmethod
    def validate_user_type(cls, v):
        if len(v) == 0:
            raise ValueError("Please select at least one user type")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "user_type": [
                    "General Contractor",
                    "Subcontractor",
                    "Builder",
                ],
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
    business_website_url: Optional[str] = None
    state_license_number: Optional[str] = None
    license_picture_filename: Optional[str] = None
    referrals_filename: Optional[str] = None
    job_photos_filename: Optional[str] = None
    license_expiration_date: Optional[date] = None
    license_status: Optional[str] = None
    user_type: Optional[List[str]] = None
    state: Optional[List[str]] = None  # Changed to List[str] to match database ARRAY
    country_city: Optional[List[str]] = (
        None  # Changed to List[str] to match database ARRAY
    )
    registration_step: int
    is_completed: bool

    class Config:
        from_attributes = True


class ContractorAccount(BaseModel):
    name: Optional[str] = None
    email: EmailStr


class ContractorAccountUpdate(BaseModel):
    name: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None

    @model_validator(mode="after")
    def validate_passwords(self):
        if (self.current_password and not self.new_password) or (
            self.new_password and not self.current_password
        ):
            raise ValueError(
                "current_password and new_password are both required to change password"
            )
        return self


class ContractorBusinessDetails(BaseModel):
    company_name: Optional[str] = None
    phone_number: Optional[str] = None
    business_address: Optional[str] = None
    business_website_url: Optional[str] = None


class ContractorBusinessDetailsUpdate(ContractorBusinessDetails):
    pass


class ContractorLicenseInfo(BaseModel):
    state_license_number: Optional[str] = None
    license_expiration_date: Optional[date] = None
    license_status: Optional[str] = None
    license_picture_filename: Optional[str] = None


class ContractorLicenseInfoUpdate(BaseModel):
    state_license_number: Optional[str] = None
    license_expiration_date: Optional[date] = None
    license_status: Optional[str] = None


class ContractorTradeInfo(BaseModel):
    user_type: Optional[List[str]] = None


class ContractorTradeInfoUpdate(ContractorTradeInfo):
    pass


class ContractorLocationInfo(BaseModel):
    state: Optional[List[str]] = None
    country_city: Optional[List[str]] = None


class ContractorLocationInfoUpdate(BaseModel):
    state: Optional[str] = None
    country_city: Optional[str] = None
