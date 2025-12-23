from fastapi import APIRouter

from src.app.api.endpoints import (
    auth,
    contractor,
    dashboard,
    groq_email,
    jobs,
    profile,
    saved_jobs,
    subscription,
    supplier,
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
