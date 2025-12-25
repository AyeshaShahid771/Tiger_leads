from fastapi import APIRouter

from src.app.api.endpoints import (
    admin_auth,
    auth,
    contractor,
    dashboard,
    groq_email,
    jobs,
    profile,
    saved_jobs,
    subscription,
    supplier,
    admin_dashboard,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(contractor.router)
api_router.include_router(supplier.router)
api_router.include_router(subscription.router)
api_router.include_router(jobs.router)
api_router.include_router(dashboard.router)
api_router.include_router(saved_jobs.router)
api_router.include_router(profile.router)
api_router.include_router(groq_email.router)
api_router.include_router(admin_auth.router)
api_router.include_router(admin_dashboard.router)
