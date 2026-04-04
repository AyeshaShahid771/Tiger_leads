"""
Refresh Token Management Utilities

Handles creation, validation, rotation, and revocation of refresh tokens.
"""

import hashlib
import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.app.core.jwt import create_refresh_token
from src.app.models.user import RefreshToken


def hash_token(token: str) -> str:
    """Hash a token for secure storage in database."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_and_store_refresh_token(
    db: Session,
    user_id: int,
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> tuple[str, datetime]:
    """Create a new refresh token and store it in the database.

    Args:
        db: Database session
        user_id: ID of the user
        user_agent: Optional user agent string
        ip_address: Optional IP address

    Returns:
        Tuple of (refresh_token_string, expires_at)
    """
    # Create token data
    token_data = {"sub": str(user_id), "user_id": user_id, "purpose": "refresh"}

    # Generate JWT refresh token
    refresh_token, expires_at = create_refresh_token(token_data)

    # Hash the token for storage
    token_hash = hash_token(refresh_token)

    # Store in database
    db_token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        is_revoked=False,
        user_agent=user_agent[:500] if user_agent else None,
        ip_address=ip_address[:45] if ip_address else None,
    )
    db.add(db_token)
    db.commit()

    return refresh_token, expires_at


def verify_refresh_token(db: Session, token: str) -> Optional[int]:
    """Verify a refresh token and return the user_id if valid.

    Args:
        db: Database session
        token: The refresh token to verify

    Returns:
        user_id if token is valid, None otherwise
    """
    from src.app.core.jwt import verify_token as verify_jwt

    # First, verify JWT signature and expiration
    payload = verify_jwt(token)
    if not payload:
        return None

    # Check token type
    if payload.get("type") != "refresh":
        return None

    user_id = payload.get("user_id")
    if not user_id:
        return None

    # Check if token exists in database and is not revoked
    token_hash = hash_token(token)
    db_token = (
        db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    )

    if not db_token:
        return None

    if db_token.is_revoked:
        return None

    if db_token.expires_at < datetime.utcnow():
        return None

    # Update last used timestamp
    db_token.last_used_at = datetime.utcnow()
    db.commit()

    return user_id


def rotate_refresh_token(
    db: Session,
    old_token: str,
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Optional[tuple[str, datetime]]:
    """Rotate a refresh token: revoke old token and create new one.

    Args:
        db: Database session
        old_token: The current refresh token
        user_agent: Optional user agent string
        ip_address: Optional IP address

    Returns:
        Tuple of (new_token, expires_at) if successful, None otherwise
    """
    # Verify the old token first
    user_id = verify_refresh_token(db, old_token)
    if not user_id:
        return None

    # Revoke the old token
    old_token_hash = hash_token(old_token)
    db_token = (
        db.query(RefreshToken).filter(RefreshToken.token_hash == old_token_hash).first()
    )

    if db_token:
        db_token.is_revoked = True
        db.commit()

    # Create new token
    new_token, expires_at = create_and_store_refresh_token(
        db, user_id, user_agent, ip_address
    )

    return new_token, expires_at


def revoke_refresh_token(db: Session, token: str):
    """Revoke a specific refresh token."""
    token_hash = hash_token(token)
    db_token = (
        db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    )

    if db_token:
        db_token.is_revoked = True
        db.commit()


def revoke_all_user_tokens(db: Session, user_id: int):
    """Revoke all refresh tokens for a user (logout from all devices)."""
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id, RefreshToken.is_revoked == False
    ).update({"is_revoked": True})
    db.commit()


def cleanup_expired_tokens(db: Session) -> int:
    """Remove expired refresh tokens from database.

    Returns:
        Number of tokens deleted
    """
    try:
        result = db.execute(text("DELETE FROM refresh_tokens WHERE expires_at < NOW()"))
        db.commit()
        return result.rowcount
    except Exception:
        db.rollback()
        return 0
