import logging
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text

from src.app import models
from src.app.api.api import api_router
from src.app.core.database import engine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database tables
logger.info("Initializing database tables...")
try:
    # Get existing tables before creation
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    # Create all tables
    models.Base.metadata.create_all(bind=engine)

    # Auto-migration: Add missing columns if tables exist (if needed in future)
    # Uncomment and modify this section if you need to add new columns to existing tables
    # with engine.connect() as conn:
    #     try:
    #         conn.execute(text("ALTER TABLE table_name ADD COLUMN IF NOT EXISTS column_name TYPE"))
    #         conn.commit()
    #         logger.info("✓ Column migration completed")
    #     except Exception as col_error:
    #         logger.warning(f"Column migration note: {str(col_error)}")
    #         conn.rollback()

    # Get tables after creation
    inspector = inspect(engine)
    final_tables = inspector.get_table_names()

    # Log the results
    expected_tables = [
        "users",
        "notifications",
        "password_resets",
        "contractors",
        "suppliers",
        "subscriptions",
        "subscribers",
        "jobs",
        "unlocked_leads",
    ]
    for table in expected_tables:
        if table in final_tables:
            if table not in existing_tables:
                logger.info(f"✓ Table created: {table}")
            else:
                logger.info(f"✓ Table exists: {table}")
        else:
            logger.warning(f"✗ Table missing: {table}")

    logger.info("Database initialization completed successfully")
except Exception as e:
    logger.error(f"Error initializing database: {str(e)}")
    raise

app = FastAPI(title="TigerLeads API")

# Configure CORS to allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


# Custom validation error handler to log detailed errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error on {request.method} {request.url.path}")

    # Log each validation error with details
    for error in exc.errors():
        logger.error(
            f"Field: {error.get('loc')}, Error: {error.get('msg')}, Type: {error.get('type')}"
        )

    # Format error messages for user-friendly response
    error_messages = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error.get("loc", []))
        msg = error.get("msg", "Validation error")
        error_messages.append(f"{field}: {msg}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "message": "; ".join(error_messages),
            "details": error_messages,
        },
    )


app.include_router(api_router)

# Note: File uploads have been disabled for Vercel deployment
# For production, configure cloud storage (S3, Vercel Blob, etc.)
