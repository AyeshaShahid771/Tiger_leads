from fastapi import FastAPI, Request, status
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pathlib import Path
import logging

from src.app import models
from src.app.api.api import api_router
from src.app.core.database import engine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="TigerLeads API")


# Custom validation error handler to log detailed errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error on {request.method} {request.url.path}")
    
    # Log each validation error with details
    for error in exc.errors():
        logger.error(f"Field: {error.get('loc')}, Error: {error.get('msg')}, Type: {error.get('type')}")
    
    # Format error messages for user-friendly response
    error_messages = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error.get('loc', []))
        msg = error.get('msg', 'Validation error')
        error_messages.append(f"{field}: {msg}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "message": "; ".join(error_messages),
            "details": error_messages
        }
    )


app.include_router(api_router)

# Create uploads directory if it doesn't exist
uploads_dir = Path("uploads")
uploads_dir.mkdir(exist_ok=True)
(uploads_dir / "licenses").mkdir(exist_ok=True)

# Mount static files for serving uploaded images
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
