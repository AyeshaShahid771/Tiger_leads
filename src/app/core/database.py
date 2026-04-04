import os

# Example: postgresql://user:password@localhost:5432/tigerleads
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Load environment variables from .env file
load_dotenv()

password = quote_plus(
    "Xb@qeJk3"
)  # URL encode the password to handle special characters
_raw_db = os.getenv(
    "DATABASE_URL", f"postgresql://postgres:{password}@localhost:5432/Tiger_leads"
)

# Tolerate misconfigured environment values like
# "DATABASE_URL=postgresql://..." or values wrapped in quotes.
if isinstance(_raw_db, str):
    # Strip a leading literal key if accidentally included
    if _raw_db.startswith("DATABASE_URL="):
        _raw_db = _raw_db.split("=", 1)[1]

    # Strip surrounding single/double quotes
    if (_raw_db.startswith('"') and _raw_db.endswith('"')) or (
        _raw_db.startswith("'") and _raw_db.endswith("'")
    ):
        _raw_db = _raw_db[1:-1]

DATABASE_URL = _raw_db

# Create engine with connection pooling and better error handling
engine = create_engine(
    DATABASE_URL,
    pool_size=10,  # Maximum number of connections in the pool
    max_overflow=20,  # Maximum number of connections that can be created beyond pool_size
    pool_timeout=30,  # Timeout for getting a connection from the pool
    pool_recycle=3600,  # Recycle connections after 1 hour to prevent stale connections
    pool_pre_ping=True,  # Test connections before using them
    echo=False,  # Set to True for SQL query logging (debugging)
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
