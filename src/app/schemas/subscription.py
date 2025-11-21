from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel


# Subscription Schemas
class SubscriptionBase(BaseModel):
    name: str
    price: str
    tokens: int


class SubscriptionResponse(SubscriptionBase):
    id: int

    class Config:
        from_attributes = True


# Subscriber Schemas
class SubscriberCreate(BaseModel):
    subscription_id: int


class SubscriberResponse(BaseModel):
    id: int
    user_id: int
    subscription_id: Optional[int] = None
    current_credits: int
    total_spending: int
    subscription_start_date: Optional[datetime] = None
    subscription_renew_date: Optional[datetime] = None
    is_active: bool

    class Config:
        from_attributes = True


# Job/Lead Schemas
class JobBase(BaseModel):
    permit_record_number: Optional[str] = None
    date: Optional[date] = None
    permit_type: Optional[str] = None
    project_description: Optional[str] = None
    job_address: Optional[str] = None
    job_cost: Optional[str] = None
    permit_status: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    work_type: Optional[str] = None
    credit_cost: Optional[int] = 1
    category: Optional[str] = None


class JobCreate(JobBase):
    email: Optional[str] = None
    phone_number: Optional[str] = None


class JobResponse(JobBase):
    id: int
    created_at: datetime

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


# Dashboard Schema
class DashboardResponse(BaseModel):
    user_email: str
    role: str
    is_profile_complete: bool
    credit_balance: int
    credits_added_this_week: int
    active_subscription: Optional[str] = None
    subscription_renew_date: Optional[datetime] = None
    total_jobs_unlocked: int
    total_available_jobs: int
    recent_leads: List[JobResponse]
    current_page: int
    total_pages: int


# Filter Request
class FilterRequest(BaseModel):
    cities: Optional[List[str]] = None
    countries: Optional[List[str]] = None
    work_types: Optional[List[str]] = None
    states: Optional[List[str]] = None
