from fastapi import APIRouter

from src.app.api.endpoints import (
    admin_auth,
    admin_dashboard,
    ai_job_matching,
    auth,
    contractor,
    dashboard,
    groq_email,
    jobs,
    profile,
    push,
    saved_jobs,
    subscription,
    supplier,
    two_factor,
    two_factor_recovery,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(two_factor.router)  # 2FA endpoints
api_router.include_router(two_factor_recovery.router)  # 2FA recovery endpoints
api_router.include_router(push.router)  # Push notification endpoints
api_router.include_router(contractor.router)
api_router.include_router(supplier.router)
api_router.include_router(subscription.router)
api_router.include_router(jobs.router)
api_router.include_router(dashboard.router)
api_router.include_router(saved_jobs.router)
api_router.include_router(profile.router)
api_router.include_router(groq_email.router)
api_router.include_router(ai_job_matching.router)
api_router.include_router(admin_auth.router)
api_router.include_router(admin_dashboard.router)
