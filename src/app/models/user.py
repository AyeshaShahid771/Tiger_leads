from sqlalchemy import (
    ARRAY,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.sql import func

from src.app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    email_verified = Column(Boolean, default=False)
    verification_code = Column(String(10), nullable=True)
    code_expires_at = Column(DateTime, nullable=True)
    role = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    type = Column(String(50))
    message = Column(String)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class PasswordReset(Base):
    __tablename__ = "password_resets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class Contractor(Base):
    __tablename__ = "contractors"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Step 1: Basic Business Information
    company_name = Column(String(255), nullable=True)
    primary_contact_name = Column(String(255), nullable=True)
    phone_number = Column(String(20), nullable=True)
    website_url = Column(String(500), nullable=True)
    business_address = Column(Text, nullable=True)
    business_type = Column(String(100), nullable=True)  # Industry classification
    years_in_business = Column(Integer, nullable=True)

    # Step 2: License Information
    state_license_number = Column(String(100), nullable=True)
    license_picture = Column(LargeBinary, nullable=True)  # Store image binary data
    license_picture_filename = Column(String(255), nullable=True)  # Original filename
    license_picture_content_type = Column(
        String(50), nullable=True
    )  # MIME type (image/jpeg, image/png)
    license_expiration_date = Column(Date, nullable=True)
    license_status = Column(String(20), nullable=True)  # Active, Expired, etc.

    # Step 3: Trade Information (up to 5 business types)
    work_type = Column(String(50), nullable=True)  # Residential, Commercial, Industrial
    business_types = Column(Text, nullable=True)  # Store as JSON string array

    # Step 4: Service Jurisdictions
    service_state = Column(String(100), nullable=True)
    service_zip_code = Column(String(20), nullable=True)

    # Tracking fields
    registration_step = Column(Integer, default=0)  # Track which step user is on (0-4)
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Step 1: Basic Business Information
    company_name = Column(String(255), nullable=True)
    primary_contact_name = Column(String(255), nullable=True)
    phone_number = Column(String(20), nullable=True)
    website_url = Column(String(500), nullable=True)
    years_in_business = Column(Integer, nullable=True)
    business_type = Column(
        String(100), nullable=True
    )  # Manufacturer, Distributor, etc.

    # Step 2: Service Area / Delivery Radius
    service_states = Column(Text, nullable=True)  # JSON array of states
    service_zipcode = Column(String(20), nullable=True)
    onsite_delivery = Column(String(10), nullable=True)  # "yes" or "no"
    delivery_lead_time = Column(
        String(50), nullable=True
    )  # Same Day, Next Day, 2-4 Days, 5+ Days

    # Step 3: Supplier Capabilities
    carries_inventory = Column(String(10), nullable=True)  # "yes" or "no"
    offers_custom_orders = Column(String(10), nullable=True)  # "yes" or "no"
    minimum_order_amount = Column(String(100), nullable=True)
    accepts_urgent_requests = Column(String(10), nullable=True)  # "yes" or "no"
    offers_credit_accounts = Column(String(10), nullable=True)  # "yes" or "no"

    # Step 4: Product Categories
    product_categories = Column(
        Text, nullable=True
    )  # JSON array of selected categories

    # Tracking fields
    registration_step = Column(Integer, default=0)  # Track which step user is on (0-4)
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
