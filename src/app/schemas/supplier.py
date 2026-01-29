from datetime import date
from typing import List, Optional


from pydantic import BaseModel, EmailStr, field_validator


# Step 1: Basic Business Information
class SupplierStep1(BaseModel):
    company_name: Optional[str] = None
    primary_contact_name: Optional[str] = None
    phone_number: Optional[str] = None
    website_url: Optional[str] = None
    business_address: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "company_name": "ABC Supply Co",
                "primary_contact_name": "Jane Smith",
                "phone_number": "(555) 123-4567",
                "website_url": "https://abcsupply.com",
                "business_address": "123 Industrial Pkwy, Dallas, TX",
            }
        }


# Step 2: Service Area / Delivery Radius
class SupplierStep2(BaseModel):
    service_states: Optional[List[str]] = None  # Multi-select states
    country_city: Optional[str] = None  # City/county

    class Config:
        json_schema_extra = {
            "example": {
                "service_states": ["Florida", "Georgia", "Alabama"],
                "country_city": "USA/Miami",
            }
        }




# License Info Model (shared with contractor)
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
                "status": "Active"
            }
        }


# Step 3: Company Credentials (Text Only - No Files)
class SupplierStep3(BaseModel):
    user_type: Optional[List[str]] = None  # Array of user types

    class Config:
        json_schema_extra = {
            "example": {
                "user_type": [
                    "Supplier",
                    "Distributor",
                    "Manufacturer",
                ],
            }
        }

# Step 4: User Type
class SupplierStep4(BaseModel):
    licenses: Optional[List[LicenseInfo]] = []

    class Config:
        json_schema_extra = {
            "example": {
                "licenses": [
                    {
                        "license_number": "LIC-12345",
                        "expiration_date": "2026-12-31",
                        "status": "Active"
                    },
                    {
                        "license_number": "LIC-67890",
                        "expiration_date": "2027-06-30",
                        "status": "Pending"
                    }
                ]
            }
        }


# Response models
class SupplierStepResponse(BaseModel):
    message: str
    step_completed: int
    total_steps: int
    is_completed: bool
    next_step: Optional[int]


class SupplierProfile(BaseModel):
    id: int
    user_id: int
    # Step 1 fields
    company_name: Optional[str] = None
    primary_contact_name: Optional[str] = None
    phone_number: Optional[str] = None
    website_url: Optional[str] = None
    business_address: Optional[str] = None
    # Step 2 fields
    service_states: Optional[List[str]] = None
    country_city: Optional[List[str]] = None
    # Step 3 fields
    state_license_number: Optional[List[str]] = None  # Array of license numbers
    license_expiration_date: Optional[List[str]] = None  # Array of dates
    license_status: Optional[List[str]] = None  # Array of statuses
    license_picture_filename: Optional[str] = None
    referrals_filename: Optional[str] = None
    job_photos_filename: Optional[str] = None
    # Step 4 fields
    user_type: Optional[List[str]] = None
    # Tracking fields
    registration_step: int
    is_completed: bool

    class Config:
        from_attributes = True


class SupplierAccount(BaseModel):

    name: Optional[str] = None
    email: EmailStr


# For updating supplier account (name, password)
class SupplierAccountUpdate(BaseModel):
    name: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


# For business details endpoints
class SupplierBusinessDetails(BaseModel):
    company_name: Optional[str] = None
    primary_contact_name: Optional[str] = None
    phone_number: Optional[str] = None
    website_url: Optional[str] = None
    business_address: Optional[str] = None


class SupplierBusinessDetailsUpdate(BaseModel):
    """PATCH schema - all fields optional"""
    company_name: Optional[str] = None
    primary_contact_name: Optional[str] = None
    phone_number: Optional[str] = None
    website_url: Optional[str] = None
    business_address: Optional[str] = None


# For location info endpoints
class PendingJurisdictionResponse(BaseModel):
    """Response schema for pending jurisdiction requests"""
    id: int
    jurisdiction_type: str
    jurisdiction_value: str
    status: str
    created_at: str


class SupplierLocationInfo(BaseModel):
    service_states: Optional[List[str]] = None
    country_city: Optional[List[str]] = None
    pending_jurisdictions: Optional[List[PendingJurisdictionResponse]] = None


class SupplierLocationInfoUpdate(BaseModel):
    """PATCH schema - new values create pending jurisdictions"""
    state: Optional[str] = None
    country_city: Optional[str] = None


# File metadata schema
class FileMetadata(BaseModel):
    """Metadata for uploaded files"""
    filename: str
    size: int
    content_type: Optional[str] = None


# For license info endpoints
class SupplierLicenseInfo(BaseModel):
    state_license_number: Optional[List[str]] = None  # Array of license numbers
    license_expiration_date: Optional[List[str]] = None  # Array of dates
    license_status: Optional[List[str]] = None  # Array of statuses
    license_picture: List[FileMetadata] = []
    referrals: List[FileMetadata] = []
    job_photos: List[FileMetadata] = []


class SupplierLicenseInfoUpdate(BaseModel):
    """PATCH schema - license fields as JSON arrays"""
    state_license_number: Optional[List[str]] = None
    license_expiration_date: Optional[List[str]] = None
    license_status: Optional[List[str]] = None


# User type endpoints
class SupplierUserType(BaseModel):
    user_type: Optional[List[str]] = None


class SupplierUserTypeUpdate(BaseModel):
    """PATCH schema - appends to existing user_type array"""
    user_type: Optional[List[str]] = None
