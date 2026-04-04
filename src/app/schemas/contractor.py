from datetime import date
from typing import List, Optional

from pydantic import BaseModel, EmailStr, field_validator, model_validator


# Step 1: Basic Business Information
class ContractorStep1(BaseModel):
    company_name: Optional[str] = None
    primary_contact_name: Optional[str] = None
    phone_number: Optional[str] = None
    business_address: Optional[str] = None
    business_website_url: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "company_name": "BuildPro Contractors",
                "primary_contact_name": "John Smith",
                "phone_number": "+91 88555 22789",
                "business_address": "221 Riverside Road, Pune",
                "business_website_url": "https://www.buildprocontractors.com",
            }
        }


# Step 2: Service Jurisdictions
class ContractorStep2(BaseModel):
    state: Optional[List[str]] = None  # Array of states
    country_city: Optional[List[str]] = None  # Array of cities

    class Config:
        json_schema_extra = {
            "example": {
                "state": ["New York", "Texas", "California"],
                "country_city": ["USA/New York", "USA/Los Angeles"],
            }
        }


# License Info Model
class LicenseInfo(BaseModel):
    """Individual license information"""

    license_number: str
    expiration_date: str  # Format: YYYY-MM-DD
    status: str  # Active, Expired, Pending, Suspended

    class Config:
        json_schema_extra = {
            "example": {
                "license_number": "CA-123456",
                "expiration_date": "2025-12-31",
                "status": "Active",
            }
        }


# Step 3: Trade Information
class ContractorStep3(BaseModel):
    user_type: Optional[List[str]] = None  # Array of user types

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


# Step 4: License Information
class ContractorStep4(BaseModel):
    licenses: Optional[List[LicenseInfo]] = []

    class Config:
        json_schema_extra = {
            "example": {
                "licenses": [
                    {
                        "license_number": "CA-123456",
                        "expiration_date": "2025-12-31",
                        "status": "Active",
                    },
                    {
                        "license_number": "NV-789012",
                        "expiration_date": "2026-06-30",
                        "status": "Pending",
                    },
                ]
            }
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
    state_license_number: Optional[List[str]] = None  # Array of license numbers
    license_picture_filename: Optional[str] = None
    referrals_filename: Optional[str] = None
    job_photos_filename: Optional[str] = None
    license_expiration_date: Optional[List[str]] = None  # Array of dates
    license_status: Optional[List[str]] = None  # Array of statuses
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
    user_id: int
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


class ContractorBusinessDetailsUpdate(BaseModel):
    """PATCH schema - all fields optional"""

    company_name: Optional[str] = None
    phone_number: Optional[str] = None
    business_address: Optional[str] = None
    business_website_url: Optional[str] = None


class FileMetadata(BaseModel):
    """Metadata for uploaded files"""

    filename: str
    size: int
    content_type: Optional[str] = None


class ContractorLicenseInfo(BaseModel):
    state_license_number: Optional[List[str]] = None  # Array of license numbers
    license_expiration_date: Optional[List[str]] = None  # Array of dates
    license_status: Optional[List[str]] = None  # Array of statuses
    license_picture: List[FileMetadata] = []
    referrals: List[FileMetadata] = []
    job_photos: List[FileMetadata] = []


class ContractorLicenseInfoUpdate(BaseModel):
    """PATCH schema - license fields as JSON arrays"""

    state_license_number: Optional[List[str]] = None
    license_expiration_date: Optional[List[str]] = None
    license_status: Optional[List[str]] = None


class PendingUserTypeResponse(BaseModel):
    """Response schema for pending user type requests"""

    id: int
    user_role: str
    user_type_value: str
    status: str
    rejection_note: Optional[str] = None
    created_at: str


class ContractorTradeInfo(BaseModel):
    message: Optional[str] = None
    user_type: Optional[List[str]] = None
    pending_user_types: Optional[List[PendingUserTypeResponse]] = None


class ContractorTradeInfoUpdate(BaseModel):
    """PATCH schema - appends to existing user_type array"""

    user_type: Optional[List[str]] = None


class PendingJurisdictionResponse(BaseModel):
    """Response schema for pending jurisdiction requests"""

    id: int
    jurisdiction_type: str
    jurisdiction_value: str
    status: str
    rejection_note: Optional[str] = None
    created_at: str


class ContractorLocationInfo(BaseModel):
    message: Optional[str] = None
    state: Optional[List[str]] = None
    country_city: Optional[List[str]] = None
    pending_jurisdictions: Optional[List[PendingJurisdictionResponse]] = None


class ContractorLocationInfoUpdate(BaseModel):
    """PATCH schema - new values create pending jurisdictions"""

    state: Optional[str] = None
    country_city: Optional[str] = None


class UploadJobUserType(BaseModel):
    """A single user-type entry in an upload-contractor-job request."""

    user_type: str  # slug  e.g. "general_contractor"
    audience_type_names: str  # display name e.g. "General Contractor"
    offset_days: int = 0


class UploadContractorJobRequest(BaseModel):
    permit_number: Optional[str] = None
    permit_status: Optional[str] = None
    permit_type_norm: Optional[str] = None
    job_address: Optional[str] = None
    project_description: Optional[str] = None
    project_cost_total: Optional[int] = None
    contractor_name: Optional[str] = None
    contractor_company: Optional[str] = None
    contractor_email: Optional[str] = None
    contractor_phone: Optional[str] = None
    source_county: Optional[str] = None
    state: Optional[str] = None
    property_type: Optional[str] = None  # 'Residential' or 'Commercial'
    user_types: List[UploadJobUserType]
    temp_upload_id: Optional[str] = None
