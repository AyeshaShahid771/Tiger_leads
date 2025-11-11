from fastapi import APIRouter

from src.app.api.endpoints import auth

api_router = APIRouter()
api_router.include_router(auth.router)
