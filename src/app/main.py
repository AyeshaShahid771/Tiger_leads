import hashlib
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
    # Don't raise here to allow the app to start for local development or debugging
    # when the database is temporarily unreachable. In production you may want to
    # re-raise to fail fast.
    logger.warning(
        "Continuing without database connection. Some endpoints may fail until DB is available."
    )

import stripe

from src.app.services.job_cleanup_service import job_cleanup_service
from src.app.services.trial_expiry_service import trial_expiry_service
from src.app.services.job_status_service import job_status_service

app = FastAPI(title="TigerLeads API")


# Startup event: Start background services
@app.on_event("startup")
async def startup_event():
    """Start background services when the application starts."""
    logger.info("Starting background services...")
    try:
        await job_cleanup_service.start()
        logger.info("✓ Job cleanup service started successfully")
    except Exception as e:
        logger.error(f"Failed to start job cleanup service: {str(e)}")
    
    try:
        await trial_expiry_service.start()
        logger.info("✓ Trial expiry service started successfully")
    except Exception as e:
        logger.error(f"Failed to start trial expiry service: {str(e)}")
    
    try:
        await job_status_service.start()
        logger.info("✓ Job status service started successfully")
    except Exception as e:
        logger.error(f"Failed to start job status service: {str(e)}")


# Shutdown event: Stop background services
@app.on_event("shutdown")
async def shutdown_event():
    """Stop background services when the application shuts down."""
    logger.info("Stopping background services...")
    try:
        await job_cleanup_service.stop()
        logger.info("✓ Job cleanup service stopped successfully")
    except Exception as e:
        logger.error(f"Failed to stop job cleanup service: {str(e)}")
    
    try:
        await trial_expiry_service.stop()
        logger.info("✓ Trial expiry service stopped successfully")
    except Exception as e:
        logger.error(f"Failed to stop trial expiry service: {str(e)}")
    
    try:
        await job_status_service.stop()
        logger.info("✓ Job status service stopped successfully")
    except Exception as e:
        logger.error(f"Failed to stop job status service: {str(e)}")


# Log Stripe package info at startup to detect corrupted installs
try:
    logger.info(
        "stripe.__version__=%s stripe.apps_type=%s",
        getattr(stripe, "__version__", None),
        type(getattr(stripe, "apps", None)),
    )
except Exception:
    logger.exception("Failed to introspect stripe package at startup")


# Temporary request/response logging middleware to help debug webhook deliveries
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url.path}")
    try:
        response = await call_next(request)
    except Exception as e:
        logger.exception(
            f"Error while handling request {request.method} {request.url.path}: {e}"
        )
        raise
    logger.info(
        f"Response: {request.method} {request.url.path} -> {response.status_code}"
    )
    return response


# Configure CORS to allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    # Do NOT allow credentials with wildcard origin — browsers reject
    # Access-Control-Allow-Origin: * when Access-Control-Allow-Credentials: true.
    # Use False to allow all origins for API calls that don't require cookies.
    allow_credentials=False,
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


@app.get("/__stripe_status")
def stripe_status():
    """Simple verification endpoint to check deployed Stripe package version
    and a short SHA1 of the `subscription.py` file so deployments can be verified.
    """
    try:
        import stripe as _stripe

        version = getattr(_stripe, "__version__", None)
    except Exception:
        version = None

    try:
        p = Path(__file__).parent / "api" / "endpoints" / "subscription.py"
        text = p.read_text(encoding="utf-8")
        sha1 = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    except Exception:
        sha1 = None

    return {"stripe_version": version, "subscription_py_sha1": sha1}


# Note: File uploads have been disabled for Vercel deployment
# For production, configure cloud storage (S3, Vercel Blob, etc.)
