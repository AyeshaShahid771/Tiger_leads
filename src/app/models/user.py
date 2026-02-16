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
from sqlalchemy.dialects.postgresql import JSON
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
    approved_by_admin = Column(String(20), default="pending")  # pending, approved, rejected
    # Optional password hash for admin users (bcrypt)
    password_hash = Column(String, nullable=True)
    role = Column(String(20), nullable=True)  # Contractor or Supplier
    is_active = Column(Boolean, default=True)
    parent_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # Team member role for sub-users (viewer or editor)
    team_role = Column(String(20), nullable=True)  # viewer, editor (only for sub-users)
    # Explicit inviter reference for accounts created via invitation
    invited_by_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    stripe_customer_id = Column(String(255), nullable=True, unique=True, index=True)
    note = Column(Text, nullable=True)  # Admin notes about the user
    profile_picture_data = Column(LargeBinary, nullable=True)  # Profile picture binary data
    profile_picture_content_type = Column(String(50), nullable=True)  # MIME type (e.g., 'image/jpeg')
    
    # Two-Factor Authentication fields
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String(32), nullable=True)  # TOTP secret (base32 encoded)
    two_factor_backup_codes = Column(ARRAY(String), nullable=True)  # Hashed backup codes
    two_factor_enabled_at = Column(DateTime, nullable=True)  # When 2FA was enabled
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class UserInvitation(Base):
    __tablename__ = "user_invitations"

    id = Column(Integer, primary_key=True, index=True)
    inviter_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invited_email = Column(String(255), nullable=False, index=True)
    invited_name = Column(String(255), nullable=True)  # Name of invited user
    invited_phone_number = Column(String(20), nullable=True)  # Phone number of invited user
    invited_user_type = Column(ARRAY(String), nullable=True)  # User types (trades) for invited user
    role = Column(String(20), default="viewer", nullable=False)  # viewer or editor
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
    business_website_url = Column(String(500), nullable=True)

    # Step 2: License Information
    # Multiple licenses stored as JSON arrays
    state_license_number = Column(JSON, nullable=True)  # Array of license numbers: ["CA-123", "NV-456"]
    license_expiration_date = Column(JSON, nullable=True)  # Array of dates: ["2025-12-31", "2026-06-30"]
    license_status = Column(JSON, nullable=True)  # Array of statuses: ["Active", "Pending"]
    license_picture = Column(JSON, nullable=True)  # Store multiple files as JSON array

    # Optional: Referrals and Job Photos (Step 2)
    referrals = Column(JSON, nullable=True)  # Store multiple files as JSON array
    job_photos = Column(JSON, nullable=True)  # Store multiple files as JSON array

    # Step 3: Trade Information
    # `user_type` stores multiple user types for the contractor as
    # an array of strings. On PostgreSQL this will be a native array type;
    # SQLAlchemy's `ARRAY(String)` maps to that.
    user_type = Column(ARRAY(String), nullable=True)

    # Step 4: Service Jurisdictions
    service_states = Column(ARRAY(String), nullable=True)  # Array of service states
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
    business_address = Column(Text, nullable=True)

    # Step 2: Service Area / Delivery Radius
    service_states = Column(ARRAY(String), nullable=True)  # Array of states
    country_city = Column(ARRAY(String), nullable=True)  # Array of cities/counties

    # Step 3: Company Credentials (Optional File Uploads)
    # Multiple licenses stored as JSON arrays
    state_license_number = Column(JSON, nullable=True)  # Array of license numbers: ["LIC-123", "LIC-456"]
    license_expiration_date = Column(JSON, nullable=True)  # Array of dates: ["2025-12-31", "2026-06-30"]
    license_status = Column(JSON, nullable=True)  # Array of statuses: ["Active", "Pending"]
    license_picture = Column(JSON, nullable=True)  # Store multiple files as JSON array
    referrals = Column(JSON, nullable=True)  # Store multiple files as JSON array
    job_photos = Column(JSON, nullable=True)  # Store multiple files as JSON array

    # Step 4: User Type
    # `user_type` stores multiple user types for the supplier as
    # an array of strings. On PostgreSQL this will be a native array type;
    # SQLAlchemy's `ARRAY(String)` maps to that.
    user_type = Column(ARRAY(String), nullable=True)

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
    
    # Tier and Add-on Configuration
    tier_level = Column(Integer, nullable=True)  # 1=Starter, 2=Professional, 3=Enterprise
    has_stay_active_bonus = Column(Boolean, default=False)  # Available in all tiers
    has_bonus_credits = Column(Boolean, default=False)  # Available in Professional & Enterprise
    has_boost_pack = Column(Boolean, default=False)  # Available in Professional only
    
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
    purchased_seats = Column(
        Integer, default=0
    )  # Accumulated seats from previous plan purchases
    # Note: `seats_used` represents number of invited seats in use (excludes main account)
    subscription_start_date = Column(DateTime, nullable=True)
    subscription_renew_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=False)
    stripe_subscription_id = Column(String(255), nullable=True, unique=True, index=True)
    # Human-readable subscription status (active, past_due, canceled, etc.)
    subscription_status = Column(String(50), default="inactive")
    
    # Trial credits tracking
    trial_credits = Column(Integer, default=25)  # Free trial credits (25)
    trial_credits_expires_at = Column(DateTime, nullable=True)  # 14 days from signup
    trial_credits_used = Column(Boolean, default=False)  # Whether trial has been claimed
    
    # Credit freeze/lapse tracking
    frozen_credits = Column(Integer, default=0)  # Credits frozen when subscription lapses
    frozen_at = Column(DateTime, nullable=True)  # When subscription lapsed and credits froze
    last_active_date = Column(DateTime, nullable=True)  # Last date subscription was active
    
    # Add-on Credits & Seats (Unredeemed)
    stay_active_credits = Column(Integer, default=0)  # Stay Active Bonus: 30 credits
    bonus_credits = Column(Integer, default=0)  # Bonus Credits: 50 credits
    boost_pack_credits = Column(Integer, default=0)  # Boost Pack: 100 credits
    boost_pack_seats = Column(Integer, default=0)  # Boost Pack: 1 seat
    
    # Add-on Redemption Tracking
    last_stay_active_redemption = Column(DateTime, nullable=True)
    last_bonus_redemption = Column(DateTime, nullable=True)
    last_boost_redemption = Column(DateTime, nullable=True)
    
    # Auto-renew preference (default: True - user must opt-out)
    auto_renew = Column(Boolean, default=True, nullable=False)
    
    # First-time subscription tracking (for add-on grants)
    first_starter_subscription_at = Column(DateTime, nullable=True)
    first_professional_subscription_at = Column(DateTime, nullable=True)
    first_enterprise_subscription_at = Column(DateTime, nullable=True)
    first_custom_subscription_at = Column(DateTime, nullable=True)



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
    project_description = Column(Text, nullable=True)
    job_address = Column(Text, nullable=True)
    permit_status = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    queue_id = Column(Integer, nullable=True)
    rule_id = Column(Integer, nullable=True)
    recipient_group = Column(String(100), nullable=True)
    recipient_group_id = Column(Integer, nullable=True)
    day_offset = Column(Integer, default=0)
    anchor_event = Column(String(50), nullable=True)
    anchor_at = Column(DateTime, nullable=True)
    due_at = Column(DateTime, nullable=True)
    permit_id = Column(Integer, nullable=True)
    permit_number = Column(String(255), nullable=True, index=True)
    permit_type_norm = Column(String(100), nullable=True)
    project_cost_total = Column(Integer, nullable=True)
    project_cost_source = Column(String(100), nullable=True)
    source_county = Column(String(100), nullable=True)
    source_system = Column(String(100), nullable=True)
    routing_anchor_at = Column(DateTime, nullable=True)
    first_seen_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    contractor_name = Column(String(255), nullable=True)
    contractor_company = Column(String(255), nullable=True)
    contractor_email = Column(String(255), nullable=True)
    contractor_phone = Column(String(20), nullable=True)
    contact_name = Column(String(255), nullable=True)  # Contact person name
    audience_type_slugs = Column(Text, nullable=True)
    audience_type_names = Column(Text, nullable=True)
    querystring = Column(Text, nullable=True)
    trs_score = Column(Integer, nullable=True)
    uploaded_by_contractor = Column(Boolean, default=False, nullable=False)
    uploaded_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    job_review_status = Column(String(20), default="posted")
    review_posted_at = Column(DateTime, nullable=True)
    job_group_id = Column(String(100), nullable=True, index=True)  # Links jobs from same submission
    job_documents = Column(JSON, nullable=True)  # Store multiple uploaded files as JSON array
    property_type = Column(String(20), nullable=True)  # Residential or Commercial
    
    # New columns for enhanced project data
    project_number = Column(String(255), nullable=True, index=True)  # Project/permit number
    project_type = Column(String(100), nullable=True)  # Type of project
    project_sub_type = Column(String(100), nullable=True)  # Sub-type of project
    project_status = Column(String(100), nullable=True)  # Current project status
    project_cost = Column(Integer, nullable=True)  # Project cost
    project_address = Column(String(255), nullable=True)  # Project address
    owner_name = Column(String(255), nullable=True)  # Property owner name
    applicant_name = Column(String(255), nullable=True)  # Applicant name
    applicant_email = Column(String(255), nullable=True)  # Applicant email
    applicant_phone = Column(String(20), nullable=True)  # Applicant phone
    contractor_company_and_address = Column(Text, nullable=True)  # Contractor company and address
    permit_raw = Column(Text, nullable=True)  # Raw permit type description

    # Property aliases for backward compatibility with endpoint code
    @property
    def permit_type(self):
        """Alias for permit_type_norm"""
        return self.permit_type_norm
    
    @property
    def email(self):
        """Alias for contractor_email"""
        return self.contractor_email
    
    @property
    def phone_number(self):
        """Alias for contractor_phone"""
        return self.contractor_phone
    
    @property
    def job_cost(self):
        """Alias for project_cost_total"""
        return self.project_cost_total
    
    @property
    def country_city(self):
        """Alias for source_county"""
        return self.source_county


class UnlockedLead(Base):
    __tablename__ = "unlocked_leads"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id = Column(
        Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    credits_spent = Column(Integer, default=1)  # Credits used to unlock this lead
    notes = Column(Text, nullable=True)  # User's notes about this lead
    unlocked_at = Column(DateTime, server_default=func.now())
    job_snapshot = Column(JSON, nullable=True)  # Snapshot of job data at unlock time


class NotInterestedJob(Base):
    __tablename__ = "not_interested_jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id = Column(
        Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True
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
        Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    saved_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        # Ensure user can only save a job once
        {"schema": None, "extend_existing": True},
    )


class TempDocument(Base):
    __tablename__ = "temp_documents"

    id = Column(Integer, primary_key=True, index=True)
    temp_upload_id = Column(String(100), unique=True, nullable=False, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    documents = Column(JSON, nullable=False)  # Array of document objects
    linked_to_job = Column(Boolean, default=False, nullable=False)  # True when job created
    linked_to_draft = Column(Boolean, default=False, nullable=False)  # True when draft created
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)  # Auto-delete after 1 hour if not linked


class DraftJob(Base):
    __tablename__ = "draft_jobs"

    id = Column(Integer, primary_key=True, index=True)
    
    # User who created the draft
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Job details - same fields as Job table
    permit_number = Column(String(255), nullable=True)
    permit_type_norm = Column(String(100), nullable=True)
    audience_type_slugs = Column(Text, nullable=True)  # For matching (same as Job model)
    audience_type_names = Column(String(255), nullable=True)  # Human-readable audience type names
    project_description = Column(Text, nullable=True)
    job_address = Column(Text, nullable=True)
    project_cost_total = Column(Integer, nullable=True)
    permit_status = Column(String(100), nullable=True)
    contractor_email = Column(String(255), nullable=True)
    contractor_phone = Column(String(20), nullable=True)
    source_county = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    contractor_name = Column(String(255), nullable=True)
    contractor_company = Column(String(255), nullable=True)
    
    # User types configuration stored as JSON
    user_types = Column(JSON, nullable=True)  # Array: [{"user_type":"electrician","offset_days":0}]
    
    # Link to temp documents
    temp_upload_id = Column(String(100), nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class PendingJurisdiction(Base):
    """
    Stores jurisdiction requests (state/city) that require admin approval.
    When users try to add new states or cities, they are stored here as 'pending'
    until an admin approves or rejects them.
    """
    __tablename__ = "pending_jurisdictions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_type = Column(String(50), nullable=False)  # 'Contractor' or 'Supplier'
    jurisdiction_type = Column(
        String(50), nullable=False
    )  # 'state', 'country_city', 'service_states'
    jurisdiction_value = Column(
        String(255), nullable=False
    )  # The actual value (e.g., 'California', 'Los Angeles')
    status = Column(
        String(20), default="pending"
    )  # 'pending', 'approved', 'rejected'
    created_at = Column(DateTime, server_default=func.now())
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(
        Integer, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )


class PushSubscription(Base):
    """
    Stores web push notification subscriptions for users.
    Used to send push notifications about new jobs every 7 days.
    """
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    endpoint = Column(String, nullable=False, unique=True)
    p256dh_key = Column(String, nullable=False)  # Encryption key
    auth_key = Column(String, nullable=False)  # Authentication secret
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    last_notified_at = Column(DateTime, nullable=True)  # Track when last notification was sent
