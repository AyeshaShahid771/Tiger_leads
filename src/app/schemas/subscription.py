from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel


# Subscription Schemas
class SubscriptionBase(BaseModel):
    name: str
    price: str
    credits: int
    max_seats: int = 1


class SubscriptionResponse(SubscriptionBase):
    id: int
    stripe_price_id: Optional[str] = None
    stripe_product_id: Optional[str] = None

    class Config:
        from_attributes = True


# Stripe Checkout Schemas
class CreateCheckoutSessionRequest(BaseModel):
    subscription_id: int


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
    seats_used: int = 1
    subscription_start_date: Optional[datetime] = None
    subscription_renew_date: Optional[datetime] = None
    is_active: bool
    stripe_subscription_id: Optional[str] = None
    subscription_status: str = "inactive"

    class Config:
        from_attributes = True


# Job/Lead Schemas
class JobBase(BaseModel):
    permit_record_number: Optional[str] = None
    date: Optional[datetime] = None
    permit_type: Optional[str] = None
    project_description: Optional[str] = None
    job_address: Optional[str] = None
    job_cost: Optional[str] = None
    permit_status: Optional[str] = None
    state: Optional[str] = None
    work_type: Optional[str] = None
    credit_cost: Optional[int] = 1
    category: Optional[str] = None


class JobCreate(JobBase):
    email: Optional[str] = None
    phone_number: Optional[str] = None


class JobResponse(JobBase):
    id: int
    email: Optional[str] = None
    phone_number: Optional[str] = None
    country_city: Optional[str] = None
    trs_score: Optional[int] = None
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
    trs_score: Optional[int] = None
    permit_type: Optional[str] = None
    country_city: Optional[str] = None
    state: Optional[str] = None


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
