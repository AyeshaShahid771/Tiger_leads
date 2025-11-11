from fastapi import FastAPI

from src.app import models
from src.app.api.api import api_router
from src.app.core.database import engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="TigerLeads API")
app.include_router(api_router)
app.include_router(api_router)
