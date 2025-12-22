from datetime import date
from typing import List, Optional

# import for schema
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
    country_city: str  # City/county
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
                "country_city": "USA/Miami",
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
    product_categories: str  # Primary category (single string)
    product_types: List[str]  # Array of detailed product types/subcategories

    @field_validator("product_types")
    @classmethod
    def validate_product_types(cls, v):
        if not isinstance(v, list) or len(v) == 0:
            raise ValueError("Please provide at least one product type")
        if len(v) > 20:
            raise ValueError("You can provide at most 20 product types")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "product_categories": "Concrete, rebar & structural materials",
                "product_types": [
                    "Ready-mix concrete",
                    "Rebar",
                    "Concrete blocks",
                ],
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
    country_city: Optional[List[str]] = (
        None  # Changed to List[str] to match database ARRAY
    )
    onsite_delivery: Optional[str] = None  # "yes" or "no"
    delivery_lead_time: Optional[str] = None
    carries_inventory: Optional[str] = None  # "yes" or "no"
    offers_custom_orders: Optional[str] = None  # "yes" or "no"
    minimum_order_amount: Optional[str] = None
    accepts_urgent_requests: Optional[str] = None  # "yes" or "no"
    offers_credit_accounts: Optional[str] = None  # "yes" or "no"
    product_categories: Optional[str] = None
    product_types: Optional[List[str]] = None
    registration_step: int
    is_completed: bool

    class Config:
        from_attributes = True
        from_attributes = True


# Account / editable pieces
from pydantic import EmailStr


class SupplierAccount(BaseModel):
    name: Optional[str] = None
    email: EmailStr


class SupplierAccountUpdate(BaseModel):
    name: Optional[str] = None


class SupplierBusinessDetails(BaseModel):
    company_name: Optional[str] = None
    phone_number: Optional[str] = None
    website_url: Optional[str] = None
    years_in_business: Optional[int] = None
    business_type: Optional[str] = None


class SupplierBusinessDetailsUpdate(SupplierBusinessDetails):
    pass


class SupplierDeliveryInfo(BaseModel):
    service_states: Optional[List[str]] = None
    country_city: Optional[str] = None
    onsite_delivery: Optional[str] = None
    delivery_lead_time: Optional[str] = None


class SupplierDeliveryInfoUpdate(SupplierDeliveryInfo):
    pass


class SupplierCapabilities(BaseModel):
    carries_inventory: Optional[str] = None
    offers_custom_orders: Optional[str] = None
    minimum_order_amount: Optional[str] = None
    accepts_urgent_requests: Optional[str] = None
    offers_credit_accounts: Optional[str] = None


class SupplierCapabilitiesUpdate(SupplierCapabilities):
    pass


class SupplierProducts(BaseModel):
    product_categories: Optional[str] = None
    product_types: Optional[List[str]] = None


class SupplierProductsUpdate(SupplierProducts):
    pass
