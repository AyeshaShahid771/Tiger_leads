from fastapi import APIRouter

from src.app.api.endpoints import auth, contractor, upload

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(contractor.router)
api_router.include_router(upload.router)
