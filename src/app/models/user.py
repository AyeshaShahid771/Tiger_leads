from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, Date, ARRAY
from sqlalchemy.sql import func

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    email_verified = Column(Boolean, default=False)
    verification_code = Column(String(10), nullable=True)
    code_expires_at = Column(DateTime, nullable=True)
    role = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    type = Column(String(50))
    message = Column(String)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class PasswordReset(Base):
    __tablename__ = "password_resets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class Contractor(Base):
    __tablename__ = "contractors"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    
    # Step 1: Basic Business Information
    company_name = Column(String(255), nullable=True)
    phone_number = Column(String(20), nullable=True)
    email_address = Column(String(255), nullable=True)
    business_address = Column(Text, nullable=True)
    business_type = Column(String(100), nullable=True)  # Industry classification
    years_in_business = Column(Integer, nullable=True)
    
    # Step 2: License Information
    state_license_number = Column(String(100), nullable=True)
    county_license = Column(String(100), nullable=True)
    occupational_license = Column(String(100), nullable=True)
    license_picture_url = Column(String(500), nullable=True)  # File upload path
    license_expiration_date = Column(Date, nullable=True)
    license_status = Column(String(20), nullable=True)  # Active, Expired, etc.
    
    # Step 3: Trade Information (up to 5 business types)
    work_type = Column(String(50), nullable=True)  # Residential, Commercial, Industrial
    business_types = Column(Text, nullable=True)  # Store as JSON string array
    
    # Step 4: Service Jurisdictions
    service_state = Column(String(100), nullable=True)
    service_zip_code = Column(String(20), nullable=True)
    
    # Tracking fields
    registration_step = Column(Integer, default=0)  # Track which step user is on (0-4)
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
