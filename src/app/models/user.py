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
    # Optional password hash for admin users (bcrypt)
    password_hash = Column(String, nullable=True)
    role = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True)
    parent_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # Explicit inviter reference for accounts created via invitation
    invited_by_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    stripe_customer_id = Column(String(255), nullable=True, unique=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class UserInvitation(Base):
    __tablename__ = "user_invitations"

    id = Column(Integer, primary_key=True, index=True)
    inviter_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invited_email = Column(String(255), nullable=False, index=True)
    invitation_token = Column(String(255), unique=True, nullable=False, index=True)
    status = Column(String(20), default="pending")  # pending, accepted, revoked
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

    # Optional: Referrals and Job Photos (Step 2)
    referrals = Column(LargeBinary, nullable=True)  # Store referrals document
    referrals_filename = Column(String(255), nullable=True)
    referrals_content_type = Column(String(50), nullable=True)
    job_photos = Column(LargeBinary, nullable=True)  # Store job photos
    job_photos_filename = Column(String(255), nullable=True)
    job_photos_content_type = Column(String(50), nullable=True)

    # Step 3: Trade Information
    # `trade_categories` is a primary category string (e.g., Residential, Commercial)
    trade_categories = Column(String(255), nullable=True)

    # `trade_specialities` stores multiple specialities for the contractor as
    # an array of strings. On PostgreSQL this will be a native array type;
    # SQLAlchemy's `ARRAY(String)` maps to that. If your DB does not support
    # native arrays, you can store JSON in a Text column instead.
    trade_specialities = Column(ARRAY(String), nullable=True)

    # Step 4: Service Jurisdictions
    state = Column(ARRAY(String), nullable=True)  # Array of states
    country_city = Column(ARRAY(String), nullable=True)  # Array of cities/counties

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
    service_states = Column(ARRAY(String), nullable=True)  # Array of states
    country_city = Column(ARRAY(String), nullable=True)  # Array of cities/counties
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
    # Primary product category for the supplier (single-string)
    product_categories = Column(String(255), nullable=True)

    # Product types stores multiple product subtypes for the supplier as
    # an array of strings. Use Postgres TEXT[] via ARRAY(String).
    product_types = Column(ARRAY(String), nullable=True)

    # Tracking fields
    registration_step = Column(Integer, default=0)  # Track which step user is on (0-4)
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(
        String(50), nullable=False
    )  # Starter, Professional, Enterprise, Custom
    price = Column(String(20), nullable=False)  # Monthly price for standard tiers
    credits = Column(Integer, nullable=False)  # Credits per month
    max_seats = Column(Integer, default=1)  # Maximum seats allowed
    # Lead access percentage for this subscription tier (e.g., 40, 75, 100)
    lead_access_pct = Column(Integer, nullable=True)
    # Human-readable lead access description (e.g., "Upto 40% of all available leads")
    lead_access = Column(String(255), nullable=True)
    credit_price = Column(
        String(20), nullable=True
    )  # Price per credit (Custom tier only)
    seat_price = Column(String(20), nullable=True)  # Price per seat (Custom tier only)
    stripe_price_id = Column(
        String(255), nullable=True, unique=True, index=True
    )  # Stripe Price ID
    stripe_product_id = Column(
        String(255), nullable=True, index=True
    )  # Stripe Product ID
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class Subscriber(Base):
    __tablename__ = "subscribers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    subscription_id = Column(
        Integer, ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True
    )
    current_credits = Column(Integer, default=0)
    total_spending = Column(Integer, default=0)  # Total credits spent
    seats_used = Column(
        Integer, default=0
    )  # Number of seats currently used (invited seats, excludes main user)
    # Note: `seats_used` represents number of invited seats in use (excludes main account)
    subscription_start_date = Column(DateTime, nullable=True)
    subscription_renew_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=False)
    stripe_subscription_id = Column(String(255), nullable=True, unique=True, index=True)


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    # Admin users are inactive by default until they complete signup/verification
    is_active = Column(Boolean, default=False)
    # Verification code + expiry for admin signup/verify (stored on admin row)
    verification_code = Column(String(10), nullable=True)
    code_expires_at = Column(DateTime, nullable=True)
    created_by = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    note = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    subscription_status = Column(
        String(50), default="inactive"
    )  # active, past_due, canceled, etc.


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    permit_record_number = Column(String(255), nullable=True, index=True)
    date = Column(Date, nullable=True)
    permit_type = Column(String(100), nullable=True)
    project_description = Column(Text, nullable=True)
    job_address = Column(Text, nullable=True)
    job_cost = Column(String(100), nullable=True)  # Project Value
    permit_status = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    phone_number = Column(String(20), nullable=True)
    country_city = Column(
        String(100), nullable=True, index=True
    )  # Combined city/county field
    state = Column(String(100), nullable=True, index=True)
    work_type = Column(String(100), nullable=True, index=True)  # For filtering
    category = Column(String(100), nullable=True, index=True)  # Lead category
    trs_score = Column(
        Integer, nullable=True
    )  # Total Relevance Score (also used as credit cost)
    # Contractor upload tracking and moderation status
    uploaded_by_contractor = Column(Boolean, default=False, nullable=False)
    uploaded_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    job_review_status = Column(
        String(20), default="posted"
    )  # pending, posted, declined
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class UnlockedLead(Base):
    __tablename__ = "unlocked_leads"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id = Column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    credits_spent = Column(Integer, default=1)  # Credits used to unlock this lead
    notes = Column(Text, nullable=True)  # User's notes about this lead
    unlocked_at = Column(DateTime, server_default=func.now())


class NotInterestedJob(Base):
    __tablename__ = "not_interested_jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id = Column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    marked_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        # Ensure user can only mark a job as not interested once
        {"schema": None, "extend_existing": True},
    )


class SavedJob(Base):
    __tablename__ = "saved_jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id = Column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    saved_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        # Ensure user can only save a job once
        {"schema": None, "extend_existing": True},
    )
