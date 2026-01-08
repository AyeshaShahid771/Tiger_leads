from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel


# Subscription Schemas
class SubscriptionBase(BaseModel):
    name: str
    price: str
    credits: int
    max_seats: int = 1
    credit_price: Optional[str] = None
    seat_price: Optional[str] = None


class SubscriptionResponse(SubscriptionBase):
    id: int
    stripe_price_id: Optional[str] = None
    stripe_product_id: Optional[str] = None

    class Config:
        from_attributes = True


# Standard Plan Response (excludes credit_price and seat_price)
class StandardPlanResponse(BaseModel):
    id: int
    name: str
    price: str
    credits: int
    max_seats: int
    # Static description of lead access per tier (returned by /subscription/plans)
    lead_access: str
    stripe_price_id: Optional[str] = None
    stripe_product_id: Optional[str] = None

    class Config:
        from_attributes = True


# Admin Update Tier Pricing Schema
class UpdateTierPricingRequest(BaseModel):
    tier_name: Optional[str] = None  # "Starter", "Professional", "Enterprise", "Custom"
    monthly_price: Optional[str] = None
    credits: Optional[int] = None
    seats: Optional[int] = None
    credit_price: Optional[str] = None  # For Custom tier only
    seat_price: Optional[str] = None  # For Custom tier only


# Admin Bulk Update All Tiers Schema
class UpdateAllTiersPricingRequest(BaseModel):
    tiers: Optional[List[UpdateTierPricingRequest]] = None  # List of tier updates


# Custom Plan Calculator Schemas
class CalculateCustomPlanRequest(BaseModel):
    credits: int  # Number of credits requested
    seats: int  # Number of seats requested


class CalculateCustomPlanResponse(BaseModel):
    credits: int
    seats: int
    credit_price: str  # Price per credit
    seat_price: str  # Price per seat
    total_credits_cost: str  # credits * credit_price
    total_seats_cost: str  # seats * seat_price
    total_price: str  # total_credits_cost + total_seats_cost
    stripe_price_id: str  # Stripe price ID for this custom configuration
    stripe_product_id: str  # Stripe product ID


# Stripe Checkout Schemas
class CreateCheckoutSessionRequest(BaseModel):
    # Either provide an existing `stripe_price_id` OR provide the custom
    # plan details below (name, credits, price, seats) for a personalized
    # checkout. All custom fields are optional so the same schema can be
    # used for both standard and custom flows.
    stripe_price_id: Optional[str] = None  # Stripe price ID for the plan
    name: Optional[str] = None
    credits: Optional[int] = None
    price: Optional[str] = None
    seats: Optional[int] = None


class CreateCheckoutSessionResponse(BaseModel):
    checkout_url: str
    session_id: str


# Subscriber Schemas
class SubscriberCreate(BaseModel):
    subscription_id: int


class SubscriberResponse(BaseModel):
    id: int
    user_id: int
    subscription_id: Optional[int] = None
    current_credits: int
    total_spending: int
    # seats_used represents number of invited seats (excludes main account)
    seats_used: int = 0
    subscription_start_date: Optional[datetime] = None
    subscription_renew_date: Optional[datetime] = None
    is_active: bool
    stripe_subscription_id: Optional[str] = None
    subscription_status: str = "inactive"
    # Additional fields returned by /subscription/my-subscription
    plan_name: Optional[str] = None
    plan_total_credits: Optional[int] = None

    class Config:
        from_attributes = True


# Job/Lead Schemas
class JobBase(BaseModel):
    permit_number: Optional[str] = None
    permit_status: Optional[str] = None
    permit_type_norm: Optional[str] = None
    job_address: Optional[str] = None
    project_description: Optional[str] = None
    project_cost_total: Optional[int] = None
    project_cost_source: Optional[str] = None
    source_county: Optional[str] = None
    source_system: Optional[str] = None
    contractor_name: Optional[str] = None
    contractor_company: Optional[str] = None
    contractor_email: Optional[str] = None
    contractor_phone: Optional[str] = None
    audience_type_slugs: Optional[str] = None
    audience_type_names: Optional[str] = None
    state: Optional[str] = None
    anchor_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None


class JobCreate(JobBase):
    queue_id: Optional[int] = None
    rule_id: Optional[int] = None
    recipient_group: Optional[str] = None
    recipient_group_id: Optional[int] = None
    day_offset: Optional[int] = 0
    anchor_event: Optional[str] = None
    permit_id: Optional[int] = None
    routing_anchor_at: Optional[datetime] = None
    querystring: Optional[str] = None


# Contractor-specific job creation schema.
class ContractorJobCreate(JobBase):
    queue_id: Optional[int] = None
    rule_id: Optional[int] = None
    recipient_group: Optional[str] = None
    recipient_group_id: Optional[int] = None


class JobResponse(JobBase):
    id: int
    queue_id: Optional[int] = None
    rule_id: Optional[int] = None
    recipient_group: Optional[str] = None
    recipient_group_id: Optional[int] = None
    saved: bool = False
    is_unlocked: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class JobDetailResponse(JobCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# Bulk Upload Response
class BulkUploadResponse(BaseModel):
    total_rows: int
    successful: int
    failed: int
    errors: List[str] = []


# Unlocked Lead Schema
class UnlockedLeadResponse(BaseModel):
    id: int
    user_id: int
    job_id: int
    credits_spent: int
    unlocked_at: datetime
    job: JobDetailResponse

    class Config:
        from_attributes = True


# Matched Job Schema (for dashboard top 20 jobs)
class MatchedJobSummary(BaseModel):
    id: int
    permit_type_norm: Optional[str] = None
    source_county: Optional[str] = None
    state: Optional[str] = None
    project_description: Optional[str] = None
    trs_score: Optional[int] = None
    review_posted_at: Optional[datetime] = None
    saved: bool = False


# Dashboard Schema
class DashboardResponse(BaseModel):
    credit_balance: int
    credits_added_this_week: int
    plan_name: str
    renewal_date: Optional[str] = None  # e.g., "February 2025"
    profile_completion_month: Optional[str] = None  # e.g., "December 2024"
    total_jobs_unlocked: int
    top_matched_jobs: List[MatchedJobSummary]


# Filter Request
class FilterRequest(BaseModel):
    cities: Optional[List[str]] = None
    countries: Optional[List[str]] = None
    work_types: Optional[List[str]] = None
    states: Optional[List[str]] = None


# Paginated Job Response
class PaginatedJobResponse(BaseModel):
    jobs: List[JobResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# Simplified Matched Jobs Response (for pagination)
class SimplifiedMatchedJobsResponse(BaseModel):
    jobs: List[MatchedJobSummary]
    total: int
    page: int
    page_size: int
    total_pages: int
