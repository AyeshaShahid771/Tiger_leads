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
DATABASE_URL = os.getenv(
    "DATABASE_URL", f"postgresql://postgres:{password}@localhost:5432/Tiger_leads"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
