import logging
import os
import random
from datetime import datetime, timedelta
from typing import Any

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from src.app import models, schemas

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
import asyncio
import secrets

from fastapi import Depends
from sqlalchemy import text

from src.app.api.deps import get_current_user
from src.app.core.database import get_db
from src.app.core.jwt import create_access_token
from src.app.utils.email import send_password_reset_email, send_verification_email
from src.app.utils.rate_limit import rate_limit_by_email, rate_limit_by_identifier
from src.app.utils.refresh_token import (
    create_and_store_refresh_token,
    revoke_all_user_tokens,
    revoke_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Set the maximum length for bcrypt
BCRYPT_MAX_LENGTH = 72


async def cleanup_expired_unverified_users(db: Session):
    """Remove unverified users whose verification codes have expired"""
    current_time = datetime.utcnow()
    try:
        expired_users = (
            db.query(models.user.User)
            .filter(
                models.user.User.email_verified == False,
                models.user.User.code_expires_at < current_time,
            )
            .all()
        )

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
    password_bytes = password.encode("utf-8")

    # 2. Truncate to the maximum allowed length (72 bytes)
    safe_password_bytes = password_bytes[:BCRYPT_MAX_LENGTH]

    # 3. Generate salt and hash the password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(safe_password_bytes, salt)

    # 4. Return the hash as a string
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    # If there's no stored hash (invited user), treat as no match (will trigger set-password flow)
    if not hashed:
        return False

    # If hash doesn't look like a bcrypt hash, treat as no match
    if not isinstance(hashed, str) or not hashed.startswith("$2"):
        return False

    # 1. Encode both passwords to bytes
    plain_bytes = plain.encode("utf-8")[:BCRYPT_MAX_LENGTH]

    # Quick sanity checks on the stored hash to avoid ValueError from bcrypt
    try:
        hashed_bytes = hashed.encode("utf-8")
    except Exception as e:
        logger.warning(
            f"Stored password hash for user appears invalid (encoding error): {e}"
        )
        return False

    # Reject obviously-bad salts/hashes early
    if len(hashed_bytes) < 20:
        logger.warning("Stored password hash is too short to be valid bcrypt hash")
        return False

    try:
        return bcrypt.checkpw(plain_bytes, hashed_bytes)
    except ValueError as ve:
        # bcrypt raises ValueError for invalid salt; treat as non-match and log for debugging
        logger.warning(f"bcrypt ValueError during password verify: {ve}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during password verify: {e}")
        return False


@router.post("/signup")
async def signup(user: schemas.UserCreate, db: Session = Depends(get_db)):
    logger.info(f"Attempting to register user with email: {user.email}")

    # Validate email and password
    if not user.email or not user.password:
        logger.error("Email or password missing in request")
        raise HTTPException(status_code=400, detail="Email and password are required")

    existing_user = (
        db.query(models.user.User).filter(models.user.User.email == user.email).first()
    )
    if existing_user:
        if existing_user.email_verified:
            logger.warning(f"Attempt to register verified email: {user.email}")
            raise HTTPException(
                status_code=400, detail="Email already registered and verified"
            )
        else:
            # If user exists but not verified, delete the old entry and allow re-registration
            logger.info(f"Removing unverified user registration for: {user.email}")
            db.delete(existing_user)
            db.commit()

    logger.info("Hashing password")
    hashed_pw = hash_password(user.password)
    verification_code = str(random.randint(100000, 999999))
    expiry = datetime.utcnow() + timedelta(minutes=10)

    logger.info(
        f"Generated verification code: {verification_code} for email: {user.email}"
    )

    try:
        # First attempt to send a test email before creating the user
        logger.info("Attempting to validate and send verification code")
        email_sent, error_msg = await send_verification_email(
            user.email, verification_code
        )

        if not email_sent:
            logger.warning(f"Email validation failed for {user.email}: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        # Check if this email has a pending invitation
        pending_invitation = (
            db.query(models.user.UserInvitation)
            .filter(
                models.user.UserInvitation.invited_email == user.email.lower(),
                models.user.UserInvitation.status == "pending",
            )
            .first()
        )

        parent_user_id = None
        if pending_invitation:
            parent_user_id = pending_invitation.inviter_user_id
            logger.info(
                f"User {user.email} is signing up from an invitation by user ID {parent_user_id}"
            )

        # Only create user if email is valid
        logger.info("Creating new user in database")
        new_user = models.user.User(
            email=user.email,
            password_hash=hashed_pw,
            verification_code=verification_code,
            code_expires_at=expiry,
            email_verified=False,  # Explicitly set to False
            parent_user_id=parent_user_id,  # Link to inviter if this is an invited user
            team_role=(
                pending_invitation.role if pending_invitation else None
            ),  # Copy role from invitation
        )

        try:
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            logger.info(f"Successfully created user in database with ID: {new_user.id}")

            # If this was an invited user, mark invitation as accepted
            if pending_invitation:
                pending_invitation.status = "accepted"
                db.commit()
                logger.info(f"Marked invitation as accepted for {user.email}")
        except Exception as db_error:
            logger.error(f"Database error during user creation: {str(db_error)}")
            raise HTTPException(status_code=500, detail="Failed to create user account")

        return {
            "message": "User created. Please check your email for verification code.",
            "email": user.email,
            "expires_in": "10 minutes",
            "requires_verification": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during signup process: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Internal server error during signup"
        )


@router.post("/verify/{email}", response_model=schemas.Token)
def verify_email(
    email: str,
    data: schemas.VerifyEmail,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    logger.info(f"Attempting to verify email: {email}")

    user = db.query(models.user.User).filter(models.user.User.email == email).first()
    if not user:
        logger.warning(f"Verification attempt for non-existent user: {email}")
        raise HTTPException(status_code=404, detail="User not found")

    if user.email_verified:
        logger.info(
            f"Repeated verification attempt for already verified email: {email}"
        )
        raise HTTPException(status_code=400, detail="Email already verified")

    current_time = datetime.utcnow()
    if user.verification_code != data.code:
        logger.warning(f"Invalid verification code attempt for {email}")
        raise HTTPException(status_code=400, detail="Invalid verification code")

    if current_time > user.code_expires_at:
        logger.warning(f"Expired verification code used for {email}")
        raise HTTPException(
            status_code=400,
            detail="Verification code has expired. Please request a new one.",
        )

    try:
        # Update user verification status
        user.email_verified = True
        user.verification_code = None
        user.code_expires_at = None
        user.approved_by_admin = "pending"  # Set to pending on signup
        db.commit()
        logger.info(f"Email verified successfully for user: {email}")

        # Create trial subscriber with 140 free credits (14-day expiry)
        from src.app.models.user import Subscriber

        existing_subscriber = (
            db.query(Subscriber).filter(Subscriber.user_id == user.id).first()
        )
        if not existing_subscriber:
            trial_subscriber = Subscriber(
                user_id=user.id,
                current_credits=25,
                trial_credits=25,
                trial_credits_expires_at=datetime.utcnow() + timedelta(days=14),
                trial_credits_used=True,
                is_active=True,
                subscription_status="trial",
                subscription_start_date=datetime.utcnow(),
                last_active_date=datetime.utcnow(),
            )
            db.add(trial_subscriber)
            db.commit()
            logger.info(f"Trial subscriber created with 25 credits for user: {email}")

        # Create notification
        notification = models.user.Notification(
            user_id=user.id,
            type="email_verification",
            message="Your email has been verified successfully.",
        )
        db.add(notification)
        db.commit()
        logger.info(f"Verification notification created for user: {email}")

        # Create access token
        effective_user_id = user.id
        if getattr(user, "parent_user_id", None):
            effective_user_id = user.parent_user_id

        # Prevent issuing tokens to administratively disabled accounts
        if not getattr(user, "is_active", True):
            raise HTTPException(
                status_code=403,
                detail="Your account has been disabled by an administrator. Contact support for assistance.",
            )

        access_token = create_access_token(
            data={
                "sub": user.email,
                "user_id": user.id,
                "effective_user_id": effective_user_id,
            }
        )
        logger.info(f"Access token generated for verified user: {email}")

        # Create refresh token and set as HttpOnly cookie
        try:
            user_agent = request.headers.get("User-Agent")
            client_ip = request.client.host if request.client else None

            refresh_token, expires_at = create_and_store_refresh_token(
                db, user.id, user_agent, client_ip
            )

            # Set refresh token as HttpOnly cookie
            # Cookie expires with the refresh token
            response.set_cookie(
                key="refresh_token",
                value=refresh_token,
                httponly=True,
                secure=True,  # Only send over HTTPS
                samesite="lax",  # CSRF protection
                max_age=7 * 24 * 60 * 60,  # 7 days in seconds
            )
            logger.info(f"Refresh token set as HttpOnly cookie for user: {email}")
        except Exception as e:
            logger.error(f"Failed to create refresh token: {str(e)}")
            # Don't fail the verification if refresh token creation fails

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "message": "Email verified successfully",
            "effective_user_id": effective_user_id,
        }

    except Exception as e:
        logger.error(f"Error during email verification: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Error during email verification")


@router.post("/resend-otp")
async def resend_otp(data: schemas.ResendOTP, db: Session = Depends(get_db)):
    """
    Resend verification OTP to user's email.

    Rate limited to 5 requests per 5 minutes per email.

    Checks if:
    1. User exists with the provided email
    2. User has a password (has signed up)
    3. User is not yet verified

    If all conditions are met, generates a new OTP and sends it via email.
    Otherwise, returns appropriate error message.
    """
    logger.info(f"Resend OTP request for email: {data.email}")

    # Rate limit: 5 requests per 5 minutes per email
    rate_limit_by_identifier(
        f"resend_otp:{data.email.lower()}", max_attempts=5, window_seconds=300
    )

    # Find user by email
    user = (
        db.query(models.user.User).filter(models.user.User.email == data.email).first()
    )

    # Check if user exists
    if not user:
        logger.warning(f"Resend OTP attempt for non-existent user: {data.email}")
        raise HTTPException(
            status_code=404, detail="User not found. Please sign up first."
        )

    # Check if user has a password (has signed up)
    if not user.password_hash:
        logger.warning(f"Resend OTP attempt for user without password: {data.email}")
        raise HTTPException(
            status_code=400, detail="Account not found. Please sign up first."
        )

    # Check if user is already verified
    if user.email_verified:
        logger.info(f"Resend OTP attempt for already verified user: {data.email}")
        raise HTTPException(
            status_code=400, detail="Email already verified. Please login."
        )

    try:
        # Generate new verification code
        verification_code = str(random.randint(100000, 999999))
        expiry = datetime.utcnow() + timedelta(minutes=10)

        logger.info(f"Generated new verification code for: {data.email}")

        # Send verification email
        email_sent, error_msg = await send_verification_email(
            data.email, verification_code
        )

        if not email_sent:
            logger.error(
                f"Failed to send verification email to {data.email}: {error_msg}"
            )
            raise HTTPException(
                status_code=500, detail=f"Failed to send email: {error_msg}"
            )

        # Update user with new verification code
        user.verification_code = verification_code
        user.code_expires_at = expiry
        db.commit()

        logger.info(f"Successfully resent verification code to: {data.email}")

        return {
            "message": "Verification code resent successfully. Please check your email.",
            "email": data.email,
            "expires_in": "10 minutes",
            "requires_verification": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during resend OTP: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to resend verification code. Please try again.",
        )


@router.post("/login")
def login(
    credentials: schemas.UserLogin,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    # Rate limit login attempts: 5 per 5 minutes per email
    rate_limit_by_identifier(
        f"login:{credentials.email.lower()}", max_attempts=5, window_seconds=300
    )

    user = (
        db.query(models.user.User)
        .filter(models.user.User.email == credentials.email)
        .first()
    )
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # If password doesn't match, allow first-time password set for invited users
    if not verify_password(credentials.password, user.password_hash):
        # Check for a pending invitation for this email
        pending_invitation = (
            db.query(models.user.UserInvitation)
            .filter(
                models.user.UserInvitation.invited_email == user.email.lower(),
                models.user.UserInvitation.status == "pending",
            )
            .first()
        )

        if pending_invitation:
            # Treat this login attempt as first-time password set
            logger.info(f"Setting initial password for invited user {user.email}")
            user.password_hash = hash_password(credentials.password)
            user.email_verified = True
            user.parent_user_id = pending_invitation.inviter_user_id
            user.team_role = pending_invitation.role  # Copy role from invitation
            # record inviter explicitly for clarity
            if not getattr(user, "invited_by_id", None):
                user.invited_by_id = pending_invitation.inviter_user_id
            pending_invitation.status = "accepted"
            db.commit()
            # proceed as authenticated
        else:
            raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.email_verified:
        raise HTTPException(status_code=403, detail="Please verify your email first")

    # Check if user has a pending team invitation and link them
    if not user.parent_user_id:
        pending_invitation = (
            db.query(models.user.UserInvitation)
            .filter(
                models.user.UserInvitation.invited_email == user.email.lower(),
                models.user.UserInvitation.status == "pending",
            )
            .first()
        )

        if pending_invitation:
            # Link user to the inviter's account
            user.parent_user_id = pending_invitation.inviter_user_id
            user.team_role = pending_invitation.role  # Copy role from invitation
            # ensure explicit inviter recorded as well
            if not getattr(user, "invited_by_id", None):
                user.invited_by_id = pending_invitation.inviter_user_id
            pending_invitation.status = "accepted"
            db.add(user)
            db.add(pending_invitation)
            db.commit()
            logger.info(
                f"Linked existing user {user.email} (ID: {user.id}) to team via pending invitation from user {pending_invitation.inviter_user_id}"
            )

    # Create access token
    effective_user_id = user.id
    if getattr(user, "parent_user_id", None):
        effective_user_id = user.parent_user_id

    # Prevent login/token issuance for disabled accounts
    if not getattr(user, "is_active", True):
        raise HTTPException(
            status_code=403,
            detail="Your account has been disabled by an administrator. Contact support for assistance.",
        )

    # Check if 2FA is enabled
    if getattr(user, "two_factor_enabled", False):
        # User has 2FA enabled - return temp token for 2FA verification
        temp_token = create_access_token(
            data={
                "sub": user.email,
                "user_id": user.id,
                "effective_user_id": effective_user_id,
                "temp": True,  # Mark as temporary token
            }
        )

        logger.info(f"2FA required for user {user.email}")

        return {
            "requires_2fa": True,
            "temp_token": temp_token,
            "message": "Please enter your 2FA code",
        }

    # Normal login flow (no 2FA)
    try:
        access_token = create_access_token(
            data={
                "sub": user.email,
                "user_id": user.id,
                "effective_user_id": effective_user_id,
            }
        )
        logger.info(f"Access token created for user {user.email}")

        # Create refresh token and set as HttpOnly cookie
        try:
            user_agent = request.headers.get("User-Agent")
            client_ip = request.client.host if request.client else None

            refresh_token, expires_at = create_and_store_refresh_token(
                db, user.id, user_agent, client_ip
            )

            # Set refresh token as HttpOnly cookie
            response.set_cookie(
                key="refresh_token",
                value=refresh_token,
                httponly=True,
                secure=True,  # Only send over HTTPS
                samesite="lax",  # CSRF protection
                max_age=7 * 24 * 60 * 60,  # 7 days in seconds
            )
            logger.info(f"Refresh token set as HttpOnly cookie for user: {user.email}")
        except Exception as e:
            logger.error(f"Failed to create refresh token: {str(e)}")
            # Don't fail the login if refresh token creation fails

    except Exception as e:
        logger.error(f"Failed to create access token: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create access token")

    # Check if user should be redirected to dashboard
    redirect_to_dashboard = False
    is_profile_complete = False
    current_step = 0
    next_step = None
    parent = None  # Initialize parent variable

    # If this user is a sub-user (invited), treat them as already on the team's dashboard.
    # Do NOT inherit the inviter's role — sub-users keep their own role so server-side
    # endpoint restrictions for main accounts remain enforced.
    if getattr(user, "parent_user_id", None):
        try:
            parent = (
                db.query(models.user.User)
                .filter(models.user.User.id == user.parent_user_id)
                .first()
            )
            if parent:
                # Redirect sub-users straight to the dashboard of the main account
                redirect_to_dashboard = True
                is_profile_complete = True
                next_step = None
                # Do not change `user.role` here; keep the sub-user's role intact.
        except Exception:
            # If anything goes wrong during parent lookup, fall back to normal flow
            logger.exception("Error while looking up parent account for invited user")

    # Compute display values from the main account when this is a sub-user
    display_user = user
    if getattr(user, "parent_user_id", None) and parent:
        display_user = parent

    # Default display fields
    display_role = display_user.role if display_user.role else None
    display_is_profile_complete = False
    display_current_step = 0
    display_next_step = None

    try:
        if display_role == "Contractor":
            contractor = (
                db.query(models.user.Contractor)
                .filter(models.user.Contractor.user_id == display_user.id)
                .first()
            )
            if contractor:
                display_current_step = contractor.registration_step
                display_is_profile_complete = contractor.is_completed
                if contractor.is_completed:
                    redirect_to_dashboard = True
                else:
                    # Main account needs to complete profile
                    display_next_step = (
                        contractor.registration_step + 1
                        if contractor.registration_step < 4
                        else None
                    )
        elif display_role == "Supplier":
            supplier = (
                db.query(models.user.Supplier)
                .filter(models.user.Supplier.user_id == display_user.id)
                .first()
            )
            if supplier:
                display_current_step = supplier.registration_step
                display_is_profile_complete = supplier.is_completed
                if supplier.is_completed:
                    redirect_to_dashboard = True
                else:
                    # Main account needs to complete profile
                    display_next_step = (
                        supplier.registration_step + 1
                        if supplier.registration_step < 4
                        else None
                    )

        logger.info(
            f"Login successful for {user.email}, role: {display_role}, returning token"
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "requires_2fa": False,
            "redirect_to_dashboard": redirect_to_dashboard,
            "is_profile_complete": display_is_profile_complete,
            "current_step": display_current_step,
            "next_step": display_next_step,
            "role": display_role,
            "message": (
                "Welcome to Dashboard!"
                if redirect_to_dashboard
                else (
                    f"Please complete profile step {display_next_step}"
                    if display_next_step
                    else "Please set your role and complete your profile"
                )
            ),
            "effective_user_id": effective_user_id,
        }
    except Exception as e:
        logger.error(f"Error during login profile lookup: {str(e)}")
        logger.exception("Full traceback:")
        # Return token anyway, even if profile lookup fails
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "requires_2fa": False,
            "redirect_to_dashboard": False,
            "is_profile_complete": False,
            "current_step": 0,
            "next_step": None,
            "role": display_role,
            "message": "Login successful",
            "effective_user_id": effective_user_id,
        }


@router.post("/token", response_model=schemas.Token)
async def login_for_swagger(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    """
    OAuth2 compatible token endpoint for Swagger UI authentication.

    Use username field for email address.
    """
    user = (
        db.query(models.user.User)
        .filter(models.user.User.email == form_data.username)
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Run password verification in a thread to avoid blocking the event loop
    is_valid = await asyncio.to_thread(
        verify_password, form_data.password, user.password_hash
    )
    if not is_valid:
        # Allow first-time password set for invited users via swagger token flow
        pending_invitation = (
            db.query(models.user.UserInvitation)
            .filter(
                models.user.UserInvitation.invited_email == user.email.lower(),
                models.user.UserInvitation.status == "pending",
            )
            .first()
        )

        if pending_invitation:
            logger.info(
                f"Setting initial password for invited user {user.email} via token flow"
            )
            # Hash password in a threadpool as bcrypt is CPU-bound
            new_hash = await asyncio.to_thread(hash_password, form_data.password)
            user.password_hash = new_hash
            user.email_verified = True
            user.parent_user_id = pending_invitation.inviter_user_id
            user.team_role = pending_invitation.role  # Copy role from invitation
            if not getattr(user, "invited_by_id", None):
                user.invited_by_id = pending_invitation.inviter_user_id
            pending_invitation.status = "accepted"
            db.commit()
        else:
            raise HTTPException(
                status_code=401,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

    if not user.email_verified:
        raise HTTPException(status_code=403, detail="Please verify your email first")

    # Determine effective user id for display and include in token
    effective_user_id = user.id
    if getattr(user, "parent_user_id", None):
        effective_user_id = user.parent_user_id

    # Prevent token issuance for disabled users
    if not getattr(user, "is_active", True):
        raise HTTPException(
            status_code=403,
            detail="Your account has been disabled by an administrator. Contact support for assistance.",
        )

    access_token = create_access_token(
        data={
            "sub": user.email,
            "user_id": user.id,
            "effective_user_id": effective_user_id,
        }
    )

    # Compute display fields from parent/main account (do not mutate user.role)
    display_user = user
    if getattr(user, "parent_user_id", None):
        display_user = (
            db.query(models.user.User)
            .filter(models.user.User.id == user.parent_user_id)
            .first()
        ) or user

    display_role = display_user.role
    display_is_profile_complete = False
    display_current_step = 0
    display_next_step = None

    if display_role == "Contractor":
        contractor = (
            db.query(models.user.Contractor)
            .filter(models.user.Contractor.user_id == display_user.id)
            .first()
        )
        if contractor:
            display_current_step = contractor.registration_step
            display_is_profile_complete = contractor.is_completed
            if not contractor.is_completed:
                display_next_step = (
                    contractor.registration_step + 1
                    if contractor.registration_step < 4
                    else None
                )
    elif display_role == "Supplier":
        supplier = (
            db.query(models.user.Supplier)
            .filter(models.user.Supplier.user_id == display_user.id)
            .first()
        )
        if supplier:
            display_current_step = supplier.registration_step
            display_is_profile_complete = supplier.is_completed
            if not supplier.is_completed:
                display_next_step = (
                    supplier.registration_step + 1
                    if supplier.registration_step < 4
                    else None
                )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "effective_user_id": effective_user_id,
        "role": display_role,
        "is_profile_complete": display_is_profile_complete,
        "current_step": display_current_step,
        "next_step": display_next_step,
    }


@router.post("/forgot-password")
async def forgot_password(
    request: schemas.PasswordResetRequest, db: Session = Depends(get_db)
):
    """Request a password reset: generates a secure token, stores it in password_resets table and emails a reset link."""
    email = request.email
    logger.info(f"Received password reset request for: {email}")

    user = db.query(models.user.User).filter(models.user.User.email == email).first()

    # Explicit responses by case (per request):
    if not user:
        logger.info(
            f"No password reset email sent for non-existent email: {email} (no matching user found)."
        )
        raise HTTPException(
            status_code=404, detail="No account found for the provided email"
        )

    if not user.email_verified:
        logger.info(
            f"No password reset email sent for unverified user: email={email}, user_id={user.id}. Only verified users receive reset links."
        )
        raise HTTPException(
            status_code=403,
            detail="Account not verified. Please verify your email to receive password reset links.",
        )

    # Only proceed if user exists and is verified
    # generate secure token
    reset_token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(minutes=20)

    # Insert into password_resets table (user must create this table in DB)
    try:
        insert_sql = text(
            "INSERT INTO password_resets (user_id, token, expires_at, used, created_at) VALUES (:uid, :token, :expires_at, false, now())"
        )
        db.execute(
            insert_sql, {"uid": user.id, "token": reset_token, "expires_at": expires_at}
        )
        db.commit()
        logger.info(
            f"Stored password reset token for user id={user.id} (token_prefix={reset_token[:8]}...), expires_at={expires_at.isoformat()}"
        )
    except Exception as e:
        logger.error(f"Failed to store password reset record for {email}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500, detail="Failed to create password reset request"
        )

    # Build reset link - frontend should handle route /reset-password?token=<token>
    frontend_base = os.getenv("FRONTEND_URL", "https://tigerleads.vercel.app")
    reset_link = f"{frontend_base}/reset-password?token={reset_token}"

    # send reset link email
    try:
        logger.info(f"Attempting to send password reset email to {email}")
        send_start = datetime.utcnow()
        sent, err = await send_password_reset_email(email, reset_link)
        send_end = datetime.utcnow()
        duration_ms = int((send_end - send_start).total_seconds() * 1000)
        if sent:
            logger.info(
                f"Password reset email sent to {email} (duration_ms={duration_ms})"
            )
        else:
            logger.error(
                f"Failed to send reset email to {email}: {err} (duration_ms={duration_ms})"
            )
            # Delete the reset token since email failed
            try:
                delete_sql = text("DELETE FROM password_resets WHERE token = :token")
                db.execute(delete_sql, {"token": reset_token})
                db.commit()
                logger.info(f"Cleaned up reset token for {email} after send failure")
            except Exception as cleanup_err:
                logger.error(f"Failed to cleanup reset token: {str(cleanup_err)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to send password reset email. Please try again.",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending reset email to {email}: {str(e)}")
        # Delete the reset token since email failed
        try:
            delete_sql = text("DELETE FROM password_resets WHERE token = :token")
            db.execute(delete_sql, {"token": reset_token})
            db.commit()
        except Exception as cleanup_err:
            logger.error(f"Failed to cleanup reset token: {str(cleanup_err)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to send password reset email. Please try again.",
        )

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

    # Handle both timezone-aware and timezone-naive datetimes
    current_time = datetime.utcnow()
    if expires_at.tzinfo is not None:
        # expires_at is timezone-aware, make current_time aware too
        from datetime import timezone

        current_time = datetime.now(timezone.utc).replace(tzinfo=None)
        expires_at = expires_at.replace(tzinfo=None)

    if current_time > expires_at:
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

        # Set last_password_change_at to revoke all existing tokens
        user.last_password_change_at = datetime.utcnow()

        db.add(user)

        # Revoke all refresh tokens for this user
        revoke_all_user_tokens(db, user.id)
        logger.info(f"Revoked all tokens for user id {user_id} due to password reset")

        # If there's a pending invitation for this user's email, accept it and link parent_user_id
        try:
            pending_inv = (
                db.query(models.user.UserInvitation)
                .filter(
                    models.user.UserInvitation.invited_email == user.email.lower(),
                    models.user.UserInvitation.status == "pending",
                )
                .first()
            )
            if pending_inv and not user.parent_user_id:
                user.parent_user_id = pending_inv.inviter_user_id
                user.team_role = pending_inv.role  # Copy role from invitation
                if not getattr(user, "invited_by_id", None):
                    user.invited_by_id = pending_inv.inviter_user_id
                pending_inv.status = "accepted"
                db.add(user)
                db.add(pending_inv)

        except Exception as inv_err:
            logger.warning(
                f"Error while accepting pending invitation during reset: {inv_err}"
            )

        update_sql = text("UPDATE password_resets SET used = true WHERE id = :id")
        db.execute(update_sql, {"id": reset_id})
        db.commit()

        logger.info(f"Password reset successful for user id {user_id}")
        return {"message": "Password updated successfully"}

    except Exception as e:
        logger.error(f"Error updating password for user id {user_id}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to reset password")


@router.post("/set-role", response_model=schemas.RoleUpdateResponse)
def set_role(
    payload: schemas.RoleUpdate,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set the role for the currently authenticated user (Contractor or Supplier).

    The user must be authenticated with a valid access token in the Authorization header.
    The role can only be set to 'Contractor' or 'Supplier'.
    """
    # Validate and normalize the role
    role = payload.role.strip()
    allowed_roles = ("Contractor", "Supplier")

    if role not in allowed_roles:
        logger.warning(f"Invalid role attempt by user {current_user.email}: {role}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Allowed values: {', '.join(allowed_roles)}",
        )

    try:
        # Verify user exists and is active
        user = (
            db.query(models.user.User)
            .filter(models.user.User.id == current_user.id)
            .first()
        )

        if not user:
            logger.error(f"User not found during role update: {current_user.id}")
            raise HTTPException(status_code=404, detail="User not found")

        if not user.is_active:
            logger.warning(f"Inactive user attempted role update: {user.email}")
            raise HTTPException(status_code=403, detail="User account is inactive")

        # Check if role is already set to avoid unnecessary updates
        if user.role == role:
            logger.info(f"Role already set to {role} for user {user.email}")
            return {
                "message": f"Role is already set to {role}",
                "role": role,
                "email": user.email,
            }

        # Store old role for cleanup
        old_role = user.role

        # If user is switching roles, delete old profile data
        if old_role == "Contractor" and role == "Supplier":
            # Delete contractor profile
            contractor = (
                db.query(models.user.Contractor)
                .filter(models.user.Contractor.user_id == user.id)
                .first()
            )
            if contractor:
                db.delete(contractor)
                logger.info(
                    f"Deleted contractor profile for user {user.email} (switching to Supplier)"
                )

        elif old_role == "Supplier" and role == "Contractor":
            # Delete supplier profile
            supplier = (
                db.query(models.user.Supplier)
                .filter(models.user.Supplier.user_id == user.id)
                .first()
            )
            if supplier:
                db.delete(supplier)
                logger.info(
                    f"Deleted supplier profile for user {user.email} (switching to Contractor)"
                )

        # Update the role
        user.role = role
        db.add(user)
        db.commit()
        db.refresh(user)

        logger.info(f"Role updated for user {user.email}: {old_role} -> {role}")

        return {
            "message": "Role updated successfully",
            "role": role,
            "previous_role": old_role,
            "email": user.email,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update role for user id {current_user.id}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update role")


@router.get("/get-role")
def get_user_role(
    current_user: models.user.User = Depends(get_current_user),
):
    """
    Get the role of the current authenticated user.

    Returns the user's role (Contractor, Supplier, or None if not set).
    Requires authentication token in Authorization header.
    """
    logger.info(f"Role check request from user: {current_user.email}")

    return {
        "role": current_user.role,
        "email": current_user.email,
        "user_id": current_user.id,
    }


@router.get("/me")
def get_user_profile(current_user: models.user.User = Depends(get_current_user)):
    """
    Lightweight profile lookup for the authenticated user.

    Returns role, email, user_id, and whether this user is a main account or invited (has parent_user_id).
    """
    # Consider a user invited if they have either a parent link or an explicit inviter recorded
    is_invited_user = (getattr(current_user, "parent_user_id", None) is not None) or (
        getattr(current_user, "invited_by_id", None) is not None
    )
    return {
        "email": current_user.email,
        "role": current_user.role,
        "user_id": current_user.id,
        "is_invited_user": is_invited_user,
        "is_main_account": not is_invited_user,
        "parent_user_id": current_user.parent_user_id,
        "invited_by_id": getattr(current_user, "invited_by_id", None),
    }


@router.post("/logout")
def logout(
    response: Response,
    request: Request,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Logout endpoint with proper token revocation.

    - Sets last_logout_at to revoke all access tokens
    - Revokes all refresh tokens for the user
    - Clears the refresh_token HttpOnly cookie
    """
    try:
        # Set last_logout_at to current time (revokes all access tokens issued before now)
        current_user.last_logout_at = datetime.utcnow()
        db.add(current_user)
        db.commit()
        logger.info(f"Set last_logout_at for user {current_user.email}")

        # Revoke all refresh tokens for this user
        revoke_all_user_tokens(db, current_user.id)
        logger.info(f"Revoked all refresh tokens for user {current_user.email}")

        # Clear the refresh token cookie
        response.delete_cookie(
            key="refresh_token", httponly=True, secure=True, samesite="lax"
        )

        return {
            "message": "Logged out successfully. All tokens have been revoked.",
            "token_invalidated": True,
        }
    except Exception as e:
        logger.error(f"Error during logout for user {current_user.email}: {str(e)}")
        db.rollback()
        # Still clear the cookie even if DB update fails
        response.delete_cookie(
            key="refresh_token", httponly=True, secure=True, samesite="lax"
        )
        return {
            "message": "Logged out. Please delete the access token on the client.",
            "token_invalidated": True,
        }


@router.post("/refresh")
def refresh_access_token(
    request: Request, response: Response, db: Session = Depends(get_db)
):
    """
    Refresh access token using the refresh token from HttpOnly cookie.

    This implements refresh token rotation:
    - Validates the current refresh token
    - Issues a new access token
    - Issues a new refresh token (rotates the old one)
    - Old refresh token is revoked
    """
    # Get refresh token from cookie
    refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token provided")

    # Import the rotation function
    from src.app.utils.refresh_token import rotate_refresh_token, verify_refresh_token

    # Verify the refresh token and get user_id
    user_id = verify_refresh_token(db, refresh_token)

    if not user_id:
        # Invalid or expired refresh token
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token. Please login again.",
        )

    # Get user from database
    user = db.query(models.user.User).filter(models.user.User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Check if user is active
    if not getattr(user, "is_active", True):
        raise HTTPException(
            status_code=403,
            detail="Your account has been disabled by an administrator.",
        )

    # Check if user's email is verified
    if not user.email_verified:
        raise HTTPException(status_code=403, detail="Email not verified")

    try:
        # Calculate effective user ID
        effective_user_id = user.id
        if getattr(user, "parent_user_id", None):
            effective_user_id = user.parent_user_id

        # Create new access token
        access_token = create_access_token(
            data={
                "sub": user.email,
                "user_id": user.id,
                "effective_user_id": effective_user_id,
            }
        )

        # Rotate refresh token (revoke old, create new)
        user_agent = request.headers.get("User-Agent")
        client_ip = request.client.host if request.client else None

        result = rotate_refresh_token(db, refresh_token, user_agent, client_ip)

        if not result:
            raise HTTPException(
                status_code=401,
                detail="Failed to rotate refresh token. Please login again.",
            )

        new_refresh_token, expires_at = result

        # Set new refresh token as HttpOnly cookie
        response.set_cookie(
            key="refresh_token",
            value=new_refresh_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=7 * 24 * 60 * 60,  # 7 days
        )

        logger.info(f"Access token refreshed for user {user.email}")

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "message": "Token refreshed successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing token for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to refresh token")


@router.get("/registration-status")
def get_registration_status(
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the registration status for the current user based on their role.

    Returns the role (Contractor or Supplier) and whether their registration is completed.
    Requires authentication token in header.
    """
    logger.info(f"Registration status request from user: {current_user.email}")

    # Determine the display user for registration status: use parent/main account for sub-users
    display_user = current_user
    if getattr(current_user, "parent_user_id", None):
        parent = (
            db.query(models.user.User)
            .filter(models.user.User.id == current_user.parent_user_id)
            .first()
        )
        if parent:
            display_user = parent

    # Check if display user has a valid role
    if display_user.role not in ["Contractor", "Supplier"]:
        return {
            "role": display_user.role,
            "is_completed": False,
            "message": "Please set your role to 'Contractor' or 'Supplier' first",
        }

    # Check contractor registration (on display user)
    if display_user.role == "Contractor":
        contractor = (
            db.query(models.user.Contractor)
            .filter(models.user.Contractor.user_id == display_user.id)
            .first()
        )

        if not contractor:
            return {
                "role": "Contractor",
                "is_completed": False,
                "message": "Contractor registration not started",
            }

        return {
            "role": "Contractor",
            "is_completed": contractor.is_completed,
            "message": (
                "Registration completed"
                if contractor.is_completed
                else "Registration incomplete"
            ),
        }

    # Check supplier registration (on display user)
    elif display_user.role == "Supplier":
        supplier = (
            db.query(models.user.Supplier)
            .filter(models.user.Supplier.user_id == display_user.id)
            .first()
        )

        if not supplier:
            return {
                "role": "Supplier",
                "is_completed": False,
                "message": "Supplier registration not started",
            }

        return {
            "role": "Supplier",
            "is_completed": supplier.is_completed,
            "message": (
                "Registration completed"
                if supplier.is_completed
                else "Registration incomplete"
            ),
        }


@router.delete("/delete-account", status_code=200)
def delete_account(
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """Permanently delete the authenticated user's account and related data.

    This deletes the user row from the database. Rows related via
    ON DELETE CASCADE will be removed by the database. Add any
    external cleanup (Stripe customer deletion, file/object storage) here
    before the DB delete if required.
    """
    user = (
        db.query(models.user.User)
        .filter(models.user.User.id == current_user.id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Perform explicit deletion of dependent rows to avoid FK constraint errors
    try:
        # First, find any invited sub-users (users created via invitation)
        sub_users = (
            db.query(models.user.User)
            .filter(models.user.User.parent_user_id == user.id)
            .all()
        )

        sub_ids = [s.id for s in sub_users] if sub_users else []

        if sub_ids:
            # Delete dependents for sub-users in bulk
            db.query(models.user.Notification).filter(
                models.user.Notification.user_id.in_(sub_ids)
            ).delete(synchronize_session=False)
            db.query(models.user.PasswordReset).filter(
                models.user.PasswordReset.user_id.in_(sub_ids)
            ).delete(synchronize_session=False)
            db.query(models.user.UserInvitation).filter(
                models.user.UserInvitation.inviter_user_id.in_(sub_ids)
            ).delete(synchronize_session=False)
            db.query(models.user.UnlockedLead).filter(
                models.user.UnlockedLead.user_id.in_(sub_ids)
            ).delete(synchronize_session=False)
            db.query(models.user.NotInterestedJob).filter(
                models.user.NotInterestedJob.user_id.in_(sub_ids)
            ).delete(synchronize_session=False)
            db.query(models.user.SavedJob).filter(
                models.user.SavedJob.user_id.in_(sub_ids)
            ).delete(synchronize_session=False)
            db.query(models.user.Contractor).filter(
                models.user.Contractor.user_id.in_(sub_ids)
            ).delete(synchronize_session=False)
            db.query(models.user.Supplier).filter(
                models.user.Supplier.user_id.in_(sub_ids)
            ).delete(synchronize_session=False)
            db.query(models.user.Subscriber).filter(
                models.user.Subscriber.user_id.in_(sub_ids)
            ).delete(synchronize_session=False)

            # Delete the sub-user rows themselves
            db.query(models.user.User).filter(models.user.User.id.in_(sub_ids)).delete(
                synchronize_session=False
            )

        # Then delete dependents for the main user
        db.query(models.user.Notification).filter(
            models.user.Notification.user_id == user.id
        ).delete(synchronize_session=False)
        db.query(models.user.PasswordReset).filter(
            models.user.PasswordReset.user_id == user.id
        ).delete(synchronize_session=False)
        db.query(models.user.UserInvitation).filter(
            models.user.UserInvitation.inviter_user_id == user.id
        ).delete(synchronize_session=False)
        db.query(models.user.UnlockedLead).filter(
            models.user.UnlockedLead.user_id == user.id
        ).delete(synchronize_session=False)
        db.query(models.user.NotInterestedJob).filter(
            models.user.NotInterestedJob.user_id == user.id
        ).delete(synchronize_session=False)
        db.query(models.user.SavedJob).filter(
            models.user.SavedJob.user_id == user.id
        ).delete(synchronize_session=False)
        db.query(models.user.Contractor).filter(
            models.user.Contractor.user_id == user.id
        ).delete(synchronize_session=False)
        db.query(models.user.Supplier).filter(
            models.user.Supplier.user_id == user.id
        ).delete(synchronize_session=False)
        db.query(models.user.Subscriber).filter(
            models.user.Subscriber.user_id == user.id
        ).delete(synchronize_session=False)

        # Finally delete the main user row
        db.delete(user)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete account: {e}")

    return {"detail": "Account permanently deleted"}


@router.get("/status")
def get_user_status(current_user: models.user.User = Depends(get_current_user)):
    """
    Get the current approval status of the authenticated user.

    Returns the approval status set by admin:
    - "pending": Account is awaiting admin approval
    - "approved": Account has been approved by admin
    - "rejected": Account has been rejected by admin
    """
    status = getattr(current_user, "approved_by_admin", "pending")
    note = getattr(current_user, "note", None)

    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "status": status,
        "note": note,
    }
