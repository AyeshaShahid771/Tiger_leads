import logging
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.app import models, schemas
from src.app.api.deps import get_admin_by_email
from src.app.api.endpoints import auth as auth_module
from src.app.api.endpoints.auth import hash_password, verify_password
from src.app.core.database import get_db
from src.app.core.jwt import create_access_token
from src.app.utils.email import send_password_reset_email, send_verification_email

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/admin/auth", tags=["Admin Authentication"])


def _ensure_allowed(email: str, db: Session):
    """Ensure the provided email exists in the `admin_users` table and is active.

    This enforces that only addresses present in the admin table and marked active
    may use admin endpoints like login/token/forgot/reset.
    """
    if not email:
        raise HTTPException(status_code=400, detail="Email required")

    logger.debug("_ensure_allowed: checking admin existence for email=%s", email)
    admin_row = get_admin_by_email(db, email)
    logger.debug("_ensure_allowed: lookup result=%s", getattr(admin_row, "email", None))

    if not admin_row:
        logger.info("_ensure_allowed: no admin row found for %s", email)
        raise HTTPException(
            status_code=403, detail="Email not authorized for admin operations"
        )

    if not getattr(admin_row, "is_active", False):
        logger.info("_ensure_allowed: admin row exists but inactive for %s", email)
        raise HTTPException(
            status_code=403, detail="Email not authorized for admin operations"
        )
    logger.debug("_ensure_allowed: admin %s is active", email)


def _ensure_admin_exists(email: str, db: Session):
    """Ensure the provided email exists in the `admin_users` table (active or not).

    This is used for signup and verification so admins can register and then be
    activated upon successful email verification.
    """
    if not email:
        raise HTTPException(status_code=400, detail="Email required")

    logger.debug("_ensure_admin_exists: checking admin existence for email=%s", email)
    admin_row = get_admin_by_email(db, email)
    logger.debug(
        "_ensure_admin_exists: lookup returned %s", getattr(admin_row, "email", None)
    )
    if not admin_row:
        logger.info(
            "_ensure_admin_exists: email not authorized for admin operations: %s", email
        )
        raise HTTPException(
            status_code=403, detail="Email not authorized for admin operations"
        )
    logger.debug(
        "_ensure_admin_exists: admin entry exists for %s (id=%s)",
        email,
        getattr(admin_row, "id", None),
    )


def _ensure_admin_columns(db: Session):
    """Ensure `verification_code` and `code_expires_at` columns exist on admin_users.

    If missing, ALTER TABLE will add them. This makes the code robust when the
    DB schema hasn't been migrated yet.
    """
    logger.debug("_ensure_admin_columns: checking admin_users columns")
    try:
        col = db.execute(
            text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'admin_users' AND column_name = 'verification_code' LIMIT 1"
            )
        ).first()
        logger.debug("_ensure_admin_columns: column query result=%s", col)
    except Exception as e:
        logger.exception("_ensure_admin_columns: metadata check failed: %s", e)
        # If the metadata query fails, surface an error to the caller
        raise HTTPException(status_code=500, detail="Admin authorization unavailable")

    if not col:
        try:
            logger.info(
                "_ensure_admin_columns: adding missing verification/password columns to admin_users"
            )
            # Use larger field for verification_code to support URL-safe tokens for resets
            db.execute(
                text(
                    "ALTER TABLE admin_users ADD COLUMN verification_code VARCHAR(255)"
                )
            )
            db.execute(
                text(
                    "ALTER TABLE admin_users ADD COLUMN code_expires_at TIMESTAMP NULL"
                )
            )
            db.execute(
                text(
                    "ALTER TABLE admin_users ADD COLUMN password_hash VARCHAR(255) NULL"
                )
            )
            # Separate columns for password reset tokens so signup OTPs are not overwritten
            db.execute(
                text("ALTER TABLE admin_users ADD COLUMN reset_token VARCHAR(255) NULL")
            )
            db.execute(
                text(
                    "ALTER TABLE admin_users ADD COLUMN reset_token_expires_at TIMESTAMP NULL"
                )
            )
            db.commit()
            logger.info("_ensure_admin_columns: added missing admin_users columns")
        except Exception as e:
            logger.exception("_ensure_admin_columns: failed to add columns: %s", e)
            db.rollback()
            raise HTTPException(
                status_code=500, detail="Unable to prepare admin table for verification"
            )


@router.post("/signup")
async def admin_signup(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # Allow signup when admin row exists even if not active yet
    _ensure_admin_exists(user.email, db)
    # Ensure verification columns exist before writing
    _ensure_admin_columns(db)

    try:
        admin_row = get_admin_by_email(db, user.email)
        if not admin_row:
            # Shouldn't happen because _ensure_admin_exists checked, but guard
            raise HTTPException(
                status_code=403, detail="Email not authorized for admin operations"
            )

        # Generate verification code and set expiry (10 minutes)
        code = f"{secrets.randbelow(1000000):06d}"
        expiry = datetime.utcnow() + timedelta(minutes=10)

        # Persist using raw SQL to avoid ORM mapping issues
        from sqlalchemy import text

        # If a password was provided during signup, hash and persist it along with the code
        pw_hash = None
        if getattr(user, "password", None):
            pw_hash = hash_password(user.password)

        if pw_hash:
            db.execute(
                text(
                    "UPDATE admin_users SET verification_code = :code, code_expires_at = :expiry, password_hash = :pw WHERE lower(email) = lower(:email)"
                ),
                {"code": code, "expiry": expiry, "email": user.email, "pw": pw_hash},
            )
        else:
            db.execute(
                text(
                    "UPDATE admin_users SET verification_code = :code, code_expires_at = :expiry WHERE lower(email) = lower(:email)"
                ),
                {"code": code, "expiry": expiry, "email": user.email},
            )
        db.commit()

        # Send verification email (async)
        sent, err = await send_verification_email(admin_row.email, code)
        if not sent:
            logger.error(
                f"Failed to send admin verification email to {admin_row.email}: {err}"
            )
            return {"message": "Unable to send verification email at this time"}

        return {
            "message": "Verification code sent to admin email",
            "email": admin_row.email,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error during admin signup for {user.email}: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(
            status_code=500, detail="Internal server error during admin signup"
        )


@router.post("/verify/{email}")
def admin_verify_email(
    email: str, data: schemas.VerifyEmail, db: Session = Depends(get_db)
):
    # Allow verification when admin row exists (they become active after verify)
    _ensure_admin_exists(email, db)
    # Ensure verification columns exist before reading them
    _ensure_admin_columns(db)

    try:
        # Read verification fields via raw SQL
        from sqlalchemy import text

        res = db.execute(
            text(
                "SELECT id, email, verification_code, code_expires_at FROM admin_users WHERE lower(email) = lower(:email) LIMIT 1"
            ),
            {"email": email},
        ).first()
        if not res:
            raise HTTPException(status_code=404, detail="Admin entry not found")

        admin_id, admin_email, stored_code, code_expires_at = (
            res[0],
            res[1],
            res[2],
            res[3],
        )

        # Validate code
        if not stored_code or stored_code != data.code:
            raise HTTPException(status_code=400, detail="Invalid verification code")

        if not code_expires_at or datetime.utcnow() > code_expires_at:
            raise HTTPException(status_code=400, detail="Verification code has expired")

        # Activate admin and clear code via raw SQL
        db.execute(
            text(
                "UPDATE admin_users SET is_active = true, verification_code = NULL, code_expires_at = NULL WHERE id = :id"
            ),
            {"id": admin_id},
        )
        db.commit()

        # Create access token specifically for admin
        access_token = create_access_token(
            data={"sub": admin_email, "admin_user_id": admin_id}
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "message": "Admin verified and activated",
            "admin_user_id": admin_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error during admin verify for {email}: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(
            status_code=500, detail="Internal server error during admin verification"
        )


@router.post("/login")
def admin_login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    # Allow password login for admins that are active and have a stored password
    try:
        logger.info("admin_login: attempt for email=%s", credentials.email)

        _ensure_allowed(credentials.email, db)

        # Fetch admin row (includes password_hash)
        try:
            admin = get_admin_by_email(db, credentials.email)
            logger.info(
                "admin_login: got admin row for email=%s id=%s active=%s",
                credentials.email,
                getattr(admin, "id", None),
                getattr(admin, "is_active", None),
            )
        except Exception as e:
            logger.exception(
                "admin_login: error fetching admin row for %s: %s", credentials.email, e
            )
            raise HTTPException(
                status_code=500, detail="Admin authorization unavailable"
            )

        if not admin:
            logger.info("admin_login: admin not found for %s", credentials.email)
            raise HTTPException(status_code=403, detail="Admin not found")

        if not getattr(admin, "is_active", False):
            logger.info("admin_login: admin account inactive for %s", credentials.email)
            raise HTTPException(status_code=403, detail="Admin account not active")

        if not getattr(admin, "password_hash", None):
            logger.info("admin_login: no password set for %s", credentials.email)
            raise HTTPException(
                status_code=403,
                detail="Admin has no password set; use signup/verify to set a password",
            )

        # Verify password
        if not verify_password(credentials.password, admin.password_hash):
            logger.info("admin_login: invalid credentials for %s", credentials.email)
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Issue admin token
        access_token = create_access_token(
            data={"sub": admin.email, "admin_user_id": admin.id}
        )
        logger.info(
            "admin_login: success for email=%s id=%s",
            credentials.email,
            getattr(admin, "id", None),
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "message": "Admin login successful",
            "admin_user_id": admin.id,
        }

    except HTTPException:
        # Re-raise HTTPException so FastAPI will handle the response
        raise
    except Exception as e:
        logger.exception(
            "admin_login: unexpected error for %s: %s", credentials.email, e
        )
        raise HTTPException(
            status_code=500, detail="Internal server error during admin login"
        )


@router.post("/token")
def admin_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    _ensure_allowed(form_data.username, db)
    raise HTTPException(
        status_code=403,
        detail="Admin token grant disabled. Use POST /admin/auth/signup and /admin/auth/verify to obtain an admin token",
    )


@router.post("/forgot-password")
async def admin_forgot_password(
    request: schemas.PasswordResetRequest, db: Session = Depends(get_db)
):
    # Initiate an admin password reset using a URL-safe token stored on admin_users
    _ensure_allowed(request.email, db)
    # Ensure verification columns exist before writing
    _ensure_admin_columns(db)

    try:
        # Generate a secure URL-safe token and expiry (20 minutes)
        token = secrets.token_urlsafe(48)
        expiry = datetime.utcnow() + timedelta(minutes=20)

        # Persist token to admin_users.reset_token and expiry (separate from verification_code)
        from sqlalchemy import text

        db.execute(
            text(
                "UPDATE admin_users SET reset_token = :token, reset_token_expires_at = :expiry WHERE lower(email) = lower(:email)"
            ),
            {"token": token, "expiry": expiry, "email": request.email},
        )
        db.commit()

        # Build frontend reset link
        import os

        frontend_base = os.getenv(
            "FRONTEND_URL", "https://tigerleads.vercel.app/admin/reset-password "
        )
        reset_link = f"{frontend_base}?token={token}"

        # Send reset email with link
        sent, err = await send_password_reset_email(request.email, reset_link)
        if not sent:
            logger.error(
                "admin_forgot_password: failed to send reset link to %s: %s",
                request.email,
                err,
            )
            return {"message": "Unable to send password reset email at this time"}

        logger.info(
            "admin_forgot_password: sent password reset link to %s", request.email
        )
        return {"message": "Password reset link sent to admin email"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "admin_forgot_password: unexpected error for %s: %s", request.email, e
        )
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(
            status_code=500, detail="Internal server error during admin forgot-password"
        )


@router.post("/reset-password")
def admin_reset_password(
    data: schemas.PasswordResetConfirm, db: Session = Depends(get_db)
):
    # Use verification_code saved on `admin_users` as the reset token.
    # `data.token` is the verification code generated by `/forgot-password`.
    _ensure_admin_columns(db)
    try:
        from sqlalchemy import text

        res = db.execute(
            text(
                "SELECT id, email, reset_token, reset_token_expires_at FROM admin_users WHERE reset_token = :token ORDER BY id LIMIT 1"
            ),
            {"token": data.token},
        ).first()
    except Exception as e:
        logger.exception("admin_reset_password: DB error looking up token: %s", e)
        raise HTTPException(status_code=500, detail="Internal error")

    if not res:
        raise HTTPException(status_code=404, detail="Reset token not found")

    admin_id, admin_email, stored_token, token_expires_at = (
        res[0],
        res[1],
        res[2],
        res[3],
    )

    if not stored_token or stored_token != data.token:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    if not token_expires_at or datetime.utcnow() > token_expires_at:
        raise HTTPException(status_code=400, detail="Reset token has expired")

    # Hash new password and persist
    try:
        pw_hash = hash_password(data.new_password)
        db.execute(
            text(
                "UPDATE admin_users SET password_hash = :pw, reset_token = NULL, reset_token_expires_at = NULL WHERE id = :id"
            ),
            {"pw": pw_hash, "id": admin_id},
        )
        db.commit()
        logger.info(
            "admin_reset_password: password updated for admin id=%s email=%s",
            admin_id,
            admin_email,
        )
        return {"message": "Admin password updated successfully"}
    except Exception as e:
        logger.exception(
            "admin_reset_password: failed to update password for admin id=%s: %s",
            admin_id,
            e,
        )
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(
            status_code=500, detail="Internal server error during admin password reset"
        )
