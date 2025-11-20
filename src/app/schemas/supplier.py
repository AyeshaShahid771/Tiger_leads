from datetime import date
from typing import List, Optional

from pydantic import BaseModel, field_validator


# Step 1: Basic Business Information
class SupplierStep1(BaseModel):
    company_name: str
    primary_contact_name: str
    phone_number: str
    website_url: Optional[str] = None
    years_in_business: int
    business_type: (
        str  # Manufacturer, Distributor, Supplier, Rental Yard, Fabricator, Wholesaler
    )

    class Config:
        json_schema_extra = {
            "example": {
                "company_name": "ABC Supply Co",
                "primary_contact_name": "Jane Smith",
                "phone_number": "(555) 123-4567",
                "website_url": "https://abcsupply.com",
                "years_in_business": 15,
                "business_type": "Distributor",
            }
        }


# Step 2: Service Area / Delivery Radius
class SupplierStep2(BaseModel):
    service_states: List[str]  # Multi-select states
    service_zipcode: str
    onsite_delivery: str  # "yes" or "no"
    delivery_lead_time: str  # Same Day, Next Day, 2-4 Days, 5+ Days

    @field_validator("service_states")
    @classmethod
    def validate_service_states(cls, v):
        if len(v) == 0:
            raise ValueError("Please select at least one state")
        return v

    @field_validator("onsite_delivery")
    @classmethod
    def validate_onsite_delivery(cls, v):
        v_lower = v.lower()
        # Accept "yes"/"no" or "true"/"false" and convert to "yes"/"no"
        if v_lower in ["yes", "true", "1"]:
            return "yes"
        elif v_lower in ["no", "false", "0"]:
            return "no"
        else:
            raise ValueError('onsite_delivery must be "yes", "no", "true", or "false"')

    class Config:
        json_schema_extra = {
            "example": {
                "service_states": ["Florida", "Georgia", "Alabama"],
                "service_zipcode": "33101",
                "onsite_delivery": "yes",
                "delivery_lead_time": "Next Day",
            }
        }


# Step 3: Supplier Capabilities
class SupplierStep3(BaseModel):
    carries_inventory: str  # "yes" or "no"
    offers_custom_orders: str  # "yes" or "no"
    minimum_order_amount: Optional[str] = None
    accepts_urgent_requests: str  # "yes" or "no"
    offers_credit_accounts: str  # "yes" or "no"

    @field_validator("carries_inventory")
    @classmethod
    def validate_carries_inventory(cls, v):
        v_lower = v.lower()
        # Accept "yes"/"no" or "true"/"false" and convert to "yes"/"no"
        if v_lower in ["yes", "true", "1"]:
            return "yes"
        elif v_lower in ["no", "false", "0"]:
            return "no"
        else:
            raise ValueError(
                'carries_inventory must be "yes", "no", "true", or "false"'
            )

    @field_validator("offers_custom_orders")
    @classmethod
    def validate_offers_custom_orders(cls, v):
        v_lower = v.lower()
        # Accept "yes"/"no" or "true"/"false" and convert to "yes"/"no"
        if v_lower in ["yes", "true", "1"]:
            return "yes"
        elif v_lower in ["no", "false", "0"]:
            return "no"
        else:
            raise ValueError(
                'offers_custom_orders must be "yes", "no", "true", or "false"'
            )

    @field_validator("accepts_urgent_requests")
    @classmethod
    def validate_accepts_urgent_requests(cls, v):
        v_lower = v.lower()
        # Accept "yes"/"no" or "true"/"false" and convert to "yes"/"no"
        if v_lower in ["yes", "true", "1"]:
            return "yes"
        elif v_lower in ["no", "false", "0"]:
            return "no"
        else:
            raise ValueError(
                'accepts_urgent_requests must be "yes", "no", "true", or "false"'
            )

    @field_validator("offers_credit_accounts")
    @classmethod
    def validate_offers_credit_accounts(cls, v):
        v_lower = v.lower()
        # Accept "yes"/"no" or "true"/"false" and convert to "yes"/"no"
        if v_lower in ["yes", "true", "1"]:
            return "yes"
        elif v_lower in ["no", "false", "0"]:
            return "no"
        else:
            raise ValueError(
                'offers_credit_accounts must be "yes", "no", "true", or "false"'
            )

    class Config:
        json_schema_extra = {
            "example": {
                "carries_inventory": "yes",
                "offers_custom_orders": "yes",
                "minimum_order_amount": "$500",
                "accepts_urgent_requests": "yes",
                "offers_credit_accounts": "yes",
            }
        }


# Step 4: Product Categories
class SupplierStep4(BaseModel):
    product_categories: List[str]  # Multi-select from defined categories

    @field_validator("product_categories")
    @classmethod
    def validate_product_categories(cls, v):
        if len(v) == 0:
            raise ValueError("Please select at least one product category")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "product_categories": [
                    "Masonry / Concrete / CMU / Ready-Mix / Rebar",
                    "Lumber / Framing / Millwork Supply",
                    "Electrical Distributor",
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
    company_name: Optional[str] = None
    primary_contact_name: Optional[str] = None
    phone_number: Optional[str] = None
    website_url: Optional[str] = None
    years_in_business: Optional[int] = None
    business_type: Optional[str] = None
    service_states: Optional[List[str]] = None
    service_zipcode: Optional[str] = None
    onsite_delivery: Optional[str] = None  # "yes" or "no"
    delivery_lead_time: Optional[str] = None
    carries_inventory: Optional[str] = None  # "yes" or "no"
    offers_custom_orders: Optional[str] = None  # "yes" or "no"
    minimum_order_amount: Optional[str] = None
    accepts_urgent_requests: Optional[str] = None  # "yes" or "no"
    offers_credit_accounts: Optional[str] = None  # "yes" or "no"
    product_categories: Optional[List[str]] = None
    registration_step: int
    is_completed: bool

    class Config:
        from_attributes = True
