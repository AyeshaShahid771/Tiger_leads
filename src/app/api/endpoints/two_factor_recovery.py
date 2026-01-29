"""
2FA Recovery Endpoints

Additional endpoints for 2FA recovery when users lose access to their authenticator app.
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.app import models
from src.app.core.database import get_db
from src.app.core.jwt import create_access_token
from src.app.utils.email_2fa_recovery import send_2fa_recovery_email

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/2fa", tags=["Two-Factor Authentication"])


# ===========================
# Request/Response Schemas
# ===========================

class Request2FARecoveryRequest(BaseModel):
    email: str


class Request2FARecoveryResponse(BaseModel):
    message: str
    email: str
    expires_in: str


class Verify2FARecoveryRequest(BaseModel):
    email: str
    code: str


class Verify2FARecoveryResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    requires_2fa: bool = False
    role: Optional[str] = None
    message: str


# ===========================
# Endpoints
# ===========================

@router.post("/request-recovery", response_model=Request2FARecoveryResponse)
async def request_2fa_recovery(
    request: Request2FARecoveryRequest,
    db: Session = Depends(get_db),
):
    """
    Request 2FA recovery code via email.
    
    This endpoint allows users who lost access to their authenticator app
    to receive a recovery code via email. The code can be used to bypass 2FA
    and login to their account.
    
    No authentication required - only email needed.
    """
    # Find user by email
    user = (
        db.query(models.user.User)
        .filter(models.user.User.email == request.email.lower())
        .first()
    )
    
    if not user:
        # Don't reveal if email exists or not (security)
        logger.warning(f"2FA recovery requested for non-existent email: {request.email}")
        return Request2FARecoveryResponse(
            message="If the email exists and has 2FA enabled, a recovery code has been sent.",
            email=request.email,
            expires_in="10 minutes"
        )
    
    # Check if 2FA is actually enabled
    if not user.two_factor_enabled:
        logger.warning(f"2FA recovery requested but 2FA not enabled for: {request.email}")
        # Still return success message (don't reveal 2FA status)
        return Request2FARecoveryResponse(
            message="If the email exists and has 2FA enabled, a recovery code has been sent.",
            email=request.email,
            expires_in="10 minutes"
        )
    
    # Generate recovery code (6-digit OTP)
    recovery_code = str(random.randint(100000, 999999))
    expiry = datetime.utcnow() + timedelta(minutes=10)
    
    # Store recovery code in user record (reuse verification_code field)
    user.verification_code = recovery_code
    user.code_expires_at = expiry
    db.commit()
    
    # Send recovery email
    email_sent, error_msg = await send_2fa_recovery_email(user.email, recovery_code)
    
    if not email_sent:
        logger.error(f"Failed to send 2FA recovery email to {user.email}: {error_msg}")
        raise HTTPException(status_code=500, detail="Failed to send recovery email")
    
    logger.info(f"2FA recovery code sent to {user.email}")
    
    return Request2FARecoveryResponse(
        message="Recovery code sent to your email. Please check your inbox.",
        email=user.email,
        expires_in="10 minutes"
    )


@router.post("/verify-recovery", response_model=Verify2FARecoveryResponse)
def verify_2fa_recovery(
    request: Verify2FARecoveryRequest,
    db: Session = Depends(get_db),
):
    """
    Verify 2FA recovery code and login.
    
    This endpoint verifies the recovery code sent via email and returns
    an access token, effectively bypassing 2FA for this login session.
    
    After successful recovery, user should set up 2FA again.
    """
    # Find user by email
    user = (
        db.query(models.user.User)
        .filter(models.user.User.email == request.email.lower())
        .first()
    )
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or recovery code")
    
    # Check if 2FA is enabled
    if not user.two_factor_enabled:
        raise HTTPException(status_code=400, detail="2FA is not enabled for this account")
    
    # Verify recovery code
    if not user.verification_code or user.verification_code != request.code:
        raise HTTPException(status_code=401, detail="Invalid recovery code")
    
    # Check if code expired
    if not user.code_expires_at or user.code_expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Recovery code has expired")
    
    # Clear recovery code
    user.verification_code = None
    user.code_expires_at = None
    db.commit()
    
    # Create access token
    effective_user_id = user.id
    if getattr(user, "parent_user_id", None):
        effective_user_id = user.parent_user_id
    
    access_token = create_access_token(
        data={
            "sub": user.email,
            "user_id": user.id,
            "effective_user_id": effective_user_id,
        }
    )
    
    logger.info(f"2FA recovery successful for {user.email}")
    
    return Verify2FARecoveryResponse(
        access_token=access_token,
        token_type="bearer",
        requires_2fa=False,
        role=user.role,
        message="Login successful via 2FA recovery. Please set up 2FA again for security."
    )
