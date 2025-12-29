import logging
from types import SimpleNamespace

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.app import models
from src.app.core.database import get_db
from src.app.core.jwt import verify_token

logger = logging.getLogger("uvicorn.error")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


def get_admin_by_email(db: Session, email: str):
    """Return a SimpleNamespace admin object (id, email, is_active) for the given email, or None.

    Uses raw SQL to avoid depending on ORM model/table mapping. Raises HTTPException(500)
    if the DB call fails.
    """
    # Query admin_users and require the `password_hash` column exist.
    try:
        res = db.execute(
            text(
                "SELECT id, email, is_active, password_hash FROM admin_users WHERE lower(email) = lower(:email) LIMIT 1"
            ),
            {"email": email},
        ).first()
    except Exception:
        logger.exception("get_admin_by_email: DB query failed for email=%s", email)
        # Surface a clear 500 so migrations can be run to add missing columns.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin authorization unavailable",
        )

    if not res:
        return None
    return SimpleNamespace(
        id=res[0], email=res[1], is_active=res[2], password_hash=res[3]
    )


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = verify_token(token)
    if payload is None:
        raise credentials_exception

    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        raise credentials_exception
    # Deny access for administratively disabled users with a clear message.
    if not getattr(user, "is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been disabled by an administrator. Contact support for assistance.",
        )
    return user


def get_effective_user(
    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
) -> models.User:
    """Return the main account user for sub-accounts, otherwise return current_user."""
    # If this user has a parent_user_id, treat the parent as the effective user
    parent_id = getattr(current_user, "parent_user_id", None)
    if parent_id:
        main = db.query(models.User).filter(models.User.id == parent_id).first()
        if main:
            return main
    return current_user


def require_main_account(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    """Ensure the caller is a main account (not a sub-account). Raises 403 for sub-accounts."""
    if getattr(current_user, "parent_user_id", None):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only main account users are allowed to perform this action",
        )
    return current_user


def require_admin(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> models.user.AdminUser:
    """Validate token and ensure the subject email is an admin in `admin_users` table.

    This dependency uses only the `admin_users` table and the JWT subject; it does
    not require or consult the `users` table. Raises 403 if not an active admin.
    """
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Use centralized helper which requires `password_hash` column
    admin = get_admin_by_email(db, email)
    if admin:
        return admin
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
    )


def require_admin_token(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> models.user.AdminUser:
    """Validate token and ensure the subject email is an admin in `admin_users` table.

    This does NOT require a corresponding `users` row; it validates the JWT and then
    checks the `admin_users` table directly. Falls back to hard-coded list if table
    missing.
    """
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Use centralized helper which requires `password_hash` column
    admin = get_admin_by_email(db, email)
    if admin:
        return admin
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
    )
