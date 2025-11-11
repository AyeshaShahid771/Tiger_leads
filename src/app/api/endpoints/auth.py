import logging
import random
from datetime import datetime, timedelta

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.app import models, schemas

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from src.app.core.database import get_db
from src.app.core.jwt import create_access_token
from src.app.utils.email import send_verification_email, send_password_reset_email
from sqlalchemy import text
import secrets

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Set the maximum length for bcrypt
BCRYPT_MAX_LENGTH = 72

async def cleanup_expired_unverified_users(db: Session):
    """Remove unverified users whose verification codes have expired"""
    current_time = datetime.utcnow()
    try:
        expired_users = db.query(models.user.User).filter(
            models.user.User.email_verified == False,
            models.user.User.code_expires_at < current_time
        ).all()
        
        for user in expired_users:
            logger.info(f"Removing expired unverified user: {user.email}")
            db.delete(user)
        
        db.commit()
        return len(expired_users)
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        db.rollback()

# Utility functions
def hash_password(password: str) -> str:
    # 1. Encode to bytes (default is utf-8)
    password_bytes = password.encode('utf-8')
    
    # 2. Truncate to the maximum allowed length (72 bytes)
    safe_password_bytes = password_bytes[:BCRYPT_MAX_LENGTH]
    
    # 3. Generate salt and hash the password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(safe_password_bytes, salt)
    
    # 4. Return the hash as a string
    return hashed.decode('utf-8')

def verify_password(plain: str, hashed: str) -> bool:
    # 1. Encode both passwords to bytes
    plain_bytes = plain.encode('utf-8')[:BCRYPT_MAX_LENGTH]
    hashed_bytes = hashed.encode('utf-8')
    
    # 2. Use bcrypt's checkpw function to verify
    return bcrypt.checkpw(plain_bytes, hashed_bytes)

@router.post("/signup")
async def signup(user: schemas.UserCreate, db: Session = Depends(get_db)):
    logger.info(f"Attempting to register user with email: {user.email}")
    
    # Validate email and password
    if not user.email or not user.password:
        logger.error("Email or password missing in request")
        raise HTTPException(status_code=400, detail="Email and password are required")

    existing_user = db.query(models.user.User).filter(models.user.User.email == user.email).first()
    if existing_user:
        if existing_user.email_verified:
            logger.warning(f"Attempt to register verified email: {user.email}")
            raise HTTPException(status_code=400, detail="Email already registered and verified")
        else:
            # If user exists but not verified, delete the old entry and allow re-registration
            logger.info(f"Removing unverified user registration for: {user.email}")
            db.delete(existing_user)
            db.commit()

    logger.info("Hashing password")
    hashed_pw = hash_password(user.password)
    verification_code = str(random.randint(100000, 999999))
    expiry = datetime.utcnow() + timedelta(minutes=10)
    
    logger.info(f"Generated verification code: {verification_code} for email: {user.email}")

    try:
        # First attempt to send a test email before creating the user
        logger.info("Attempting to validate and send verification code")
        email_sent, error_msg = await send_verification_email(user.email, verification_code)

        if not email_sent:
            logger.warning(f"Email validation failed for {user.email}: {error_msg}")
            raise HTTPException(
                status_code=400,
                detail=error_msg
            )

        # Only create user if email is valid
        logger.info("Creating new user in database")
        new_user = models.user.User(
            email=user.email,
            password_hash=hashed_pw,
            verification_code=verification_code,
            code_expires_at=expiry,
            email_verified=False  # Explicitly set to False
        )
        
        try:
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            logger.info(f"Successfully created user in database with ID: {new_user.id}")
        except Exception as db_error:
            logger.error(f"Database error during user creation: {str(db_error)}")
            raise HTTPException(status_code=500, detail="Failed to create user account")

        return {
            "message": "User created. Please check your email for verification code.",
            "email": user.email,
            "expires_in": "10 minutes",
            "requires_verification": True
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during signup process: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error during signup")

@router.post("/verify/{email}", response_model=schemas.Token)
def verify_email(email: str, data: schemas.VerifyEmail, db: Session = Depends(get_db)):
    logger.info(f"Attempting to verify email: {email}")
    
    user = db.query(models.user.User).filter(models.user.User.email == email).first()
    if not user:
        logger.warning(f"Verification attempt for non-existent user: {email}")
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.email_verified:
        logger.info(f"Repeated verification attempt for already verified email: {email}")
        raise HTTPException(status_code=400, detail="Email already verified")

    current_time = datetime.utcnow()
    if user.verification_code != data.code:
        logger.warning(f"Invalid verification code attempt for {email}")
        raise HTTPException(status_code=400, detail="Invalid verification code")
        
    if current_time > user.code_expires_at:
        logger.warning(f"Expired verification code used for {email}")
        raise HTTPException(status_code=400, detail="Verification code has expired. Please request a new one.")

    try:
        # Update user verification status
        user.email_verified = True
        user.verification_code = None
        user.code_expires_at = None
        db.commit()
        logger.info(f"Email verified successfully for user: {email}")

        # Create notification
        notification = models.user.Notification(
            user_id=user.id,
            type="email_verification",
            message="Your email has been verified successfully."
        )
        db.add(notification)
        db.commit()
        logger.info(f"Verification notification created for user: {email}")

        # Create access token
        access_token = create_access_token(
            data={"sub": user.email, "user_id": user.id}
        )
        logger.info(f"Access token generated for verified user: {email}")

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "message": "Email verified successfully"
        }

    except Exception as e:
        logger.error(f"Error during email verification: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Error during email verification")

@router.post("/login", response_model=schemas.Token)
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.user.User).filter(models.user.User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.email_verified:
        raise HTTPException(status_code=403, detail="Please verify your email first")

    # Create access token
    access_token = create_access_token(
        data={"sub": user.email, "user_id": user.id}
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/forgot-password")
async def forgot_password(request: schemas.PasswordResetRequest, db: Session = Depends(get_db)):
    """Request a password reset: generates a secure token, stores it in password_resets table and emails a reset link."""
    email = request.email
    logger.info(f"Password reset requested for: {email}")

    user = db.query(models.user.User).filter(models.user.User.email == email).first()
    if not user:
        logger.warning(f"Password reset requested for non-existent user: {email}")
        # Keep response generic to avoid information leakage
        return {"message": "If the email exists, a password reset link has been sent"}

    # generate secure token
    reset_token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(minutes=20)

    # Insert into password_resets table (user must create this table in DB)
    try:
        insert_sql = text(
            "INSERT INTO password_resets (user_id, token, expires_at, used, created_at) VALUES (:uid, :token, :expires_at, false, now())"
        )
        db.execute(insert_sql, {"uid": user.id, "token": reset_token, "expires_at": expires_at})
        db.commit()
    except Exception as e:
        logger.error(f"Failed to store password reset record for {email}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create password reset request")

    # Build reset link - frontend should handle route /reset-password?token=<token>
    frontend_base = os.getenv("FRONTEND_URL", "http://localhost:3000/reset-password")
    reset_link = f"{frontend_base}?token={reset_token}"

    # send reset link email
    try:
        sent, err = await send_password_reset_email(email, reset_link)
        if not sent:
            logger.warning(f"Failed to send reset email to {email}: {err}")
    except Exception as e:
        logger.error(f"Error sending reset email to {email}: {str(e)}")

    return {"message": "If the email exists, a password reset link has been sent"}


@router.post("/reset-password")
def reset_password(data: schemas.PasswordResetConfirm, db: Session = Depends(get_db)):
    """Confirm password reset using token and set new password."""
    logger.info("Attempting password reset using token")

    # Find matching, unused reset record by token
    try:
        select_sql = text(
            "SELECT id, user_id, expires_at, used FROM password_resets WHERE token = :token ORDER BY created_at DESC LIMIT 1"
        )
        res = db.execute(select_sql, {"token": data.token}).first()
    except Exception as e:
        logger.error(f"DB error checking reset token: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal error")

    if not res:
        logger.warning("Invalid reset token attempt")
        raise HTTPException(status_code=400, detail="Invalid reset token")

    reset_id, user_id, expires_at, used = res
    if used:
        logger.warning("Attempt to reuse password reset token")
        raise HTTPException(status_code=400, detail="Reset token already used")

    if datetime.utcnow() > expires_at:
        logger.warning("Expired password reset token used")
        raise HTTPException(status_code=400, detail="Reset token has expired")

    user = db.query(models.user.User).filter(models.user.User.id == user_id).first()
    if not user:
        logger.error(f"Password reset token references missing user id {user_id}")
        raise HTTPException(status_code=404, detail="User not found")

    # All good: update password and mark reset as used
    try:
        hashed_pw = hash_password(data.new_password)
        user.password_hash = hashed_pw
        db.add(user)

        update_sql = text("UPDATE password_resets SET used = true WHERE id = :id")
        db.execute(update_sql, {"id": reset_id})
        db.commit()

        logger.info(f"Password reset successful for user id {user_id}")
        return {"message": "Password updated successfully"}
    except Exception as e:
        logger.error(f"Error updating password for user id {user_id}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to reset password")