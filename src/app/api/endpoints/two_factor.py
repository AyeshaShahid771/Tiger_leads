"""
Two-Factor Authentication (2FA) Endpoints

This module provides endpoints for:
- Setting up 2FA (generating QR code)
- Verifying and enabling 2FA
- Verifying 2FA during login
- Disabling 2FA
- Managing backup codes
- Checking 2FA status
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.app import models
from src.app.api.deps import get_current_user
from src.app.core.database import get_db
from src.app.core.jwt import create_access_token
from src.app.utils.two_factor import (
    format_secret_for_manual_entry,
    generate_2fa_secret,
    generate_backup_codes,
    generate_qr_code_url,
    hash_backup_code,
    verify_2fa_code,
    verify_backup_code,
)
import qrcode

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/2fa", tags=["Two-Factor Authentication"])


# ===========================
# Request/Response Schemas
# ===========================

class Setup2FAResponse(BaseModel):
    secret: str
    qr_code_url: str
    qr_code_image: str  # Base64-encoded PNG image
    manual_entry_key: str


class VerifyAndEnable2FARequest(BaseModel):
    code: str  # 6-digit TOTP code


class VerifyAndEnable2FAResponse(BaseModel):
    success: bool
    backup_codes: list[str]
    message: str


class VerifyLogin2FARequest(BaseModel):
    code: str  # 6-digit TOTP code or backup code


class VerifyLogin2FAResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class Disable2FAResponse(BaseModel):
    success: bool
    message: str


class TwoFactorStatusResponse(BaseModel):
    enabled: bool
    enabled_at: Optional[datetime] = None
    backup_codes_remaining: int


# ===========================
# Endpoints
# ===========================

@router.post("/setup")
def setup_2fa(
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Step 1: Generate QR code image for 2FA setup.
    
    Returns a PNG image that can be scanned with authenticator app.
    No password required - user is already authenticated.
    
    Frontend usage:
    <img src="/auth/2fa/setup" />
    """
    # Check if 2FA is already enabled
    if current_user.two_factor_enabled:
        raise HTTPException(
            status_code=400,
            detail="2FA is already enabled. Disable it first to set up again."
        )
    
    # Generate new secret
    secret = generate_2fa_secret()
    
    # Generate QR code URL
    qr_url = generate_qr_code_url(current_user.email, secret)
    
    # Create QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_url)
    qr.make(fit=True)
    
    # Create image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to bytes
    import io
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    # Store secret temporarily (not enabled yet)
    current_user.two_factor_secret = secret
    db.commit()
    
    logger.info(f"2FA setup initiated for user {current_user.email}")
    
    # Return PNG image
    return StreamingResponse(buffer, media_type="image/png")


@router.post("/verify-and-enable", response_model=VerifyAndEnable2FAResponse)
def verify_and_enable_2fa(
    request: VerifyAndEnable2FARequest,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Step 2: Verify TOTP code and enable 2FA.
    
    User must enter the 6-digit code from their authenticator app.
    If valid, 2FA is enabled and backup codes are generated.
    """
    # Check if secret exists
    if not current_user.two_factor_secret:
        raise HTTPException(
            status_code=400,
            detail="Please set up 2FA first using /auth/2fa/setup"
        )
    
    # Check if already enabled
    if current_user.two_factor_enabled:
        raise HTTPException(status_code=400, detail="2FA is already enabled")
    
    # Verify the code
    if not verify_2fa_code(current_user.two_factor_secret, request.code):
        raise HTTPException(status_code=400, detail="Invalid verification code")
    
    # Generate backup codes
    backup_codes = generate_backup_codes(count=5)
    
    # Hash backup codes for storage
    hashed_codes = [hash_backup_code(code) for code in backup_codes]
    
    # Enable 2FA
    current_user.two_factor_enabled = True
    current_user.two_factor_backup_codes = hashed_codes
    current_user.two_factor_enabled_at = datetime.utcnow()
    db.commit()
    
    logger.info(f"2FA enabled for user {current_user.email}")
    
    return VerifyAndEnable2FAResponse(
        success=True,
        backup_codes=backup_codes,
        message="2FA enabled successfully. Save your backup codes in a safe place!"
    )


@router.post("/verify-login", response_model=VerifyLogin2FAResponse)
def verify_login_2fa(
    request: VerifyLogin2FARequest,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Verify 2FA code during login.
    
    User provides their 2FA code after successful email/password login.
    Accepts either TOTP code or backup code.
    Returns success confirmation.
    """
    # Check if 2FA is enabled
    if not current_user.two_factor_enabled or not current_user.two_factor_secret:
        raise HTTPException(status_code=400, detail="2FA is not enabled for this user")
    
    # Try to verify as TOTP code first
    if verify_2fa_code(current_user.two_factor_secret, request.code):
        # Valid TOTP code
        logger.info(f"2FA login successful for user {current_user.email} (TOTP)")
    else:
        # Try as backup code
        is_valid, code_index = verify_backup_code(
            request.code,
            current_user.two_factor_backup_codes or []
        )
        
        if is_valid:
            # Remove used backup code
            backup_codes = current_user.two_factor_backup_codes or []
            backup_codes.pop(code_index)
            current_user.two_factor_backup_codes = backup_codes
            db.commit()
            logger.info(f"2FA login successful for user {current_user.email} (backup code)")
        else:
            raise HTTPException(status_code=400, detail="Invalid 2FA code")
    
    # Create full access token
    effective_user_id = current_user.id
    if getattr(current_user, "parent_user_id", None):
        effective_user_id = current_user.parent_user_id
    
    access_token = create_access_token(
        data={
            "sub": current_user.email,
            "user_id": current_user.id,
            "effective_user_id": effective_user_id,
        }
    )
    
    return VerifyLogin2FAResponse(
        access_token=access_token,
        token_type="bearer"
    )


@router.post("/disable", response_model=Disable2FAResponse)
def disable_2fa(
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Disable 2FA for the current user.
    
    Uses authorization token to identify user.
    No password or 2FA code required.
    """
    # Check if 2FA is enabled
    if not current_user.two_factor_enabled:
        raise HTTPException(status_code=400, detail="2FA is not enabled")
    
    # Disable 2FA
    current_user.two_factor_enabled = False
    current_user.two_factor_secret = None
    current_user.two_factor_backup_codes = None
    current_user.two_factor_enabled_at = None
    db.commit()
    
    logger.info(f"2FA disabled for user {current_user.email}")
    
    return Disable2FAResponse(
        success=True,
        message="2FA has been disabled successfully"
    )


@router.get("/status", response_model=TwoFactorStatusResponse)
def get_2fa_status(
    current_user: models.user.User = Depends(get_current_user),
):
    """
    Check 2FA status for the current user.
    
    Returns whether 2FA is enabled and how many backup codes remain.
    """
    backup_codes_remaining = 0
    if current_user.two_factor_backup_codes:
        backup_codes_remaining = len(current_user.two_factor_backup_codes)
    
    return TwoFactorStatusResponse(
        enabled=current_user.two_factor_enabled or False,
        enabled_at=current_user.two_factor_enabled_at,
        backup_codes_remaining=backup_codes_remaining
    )
