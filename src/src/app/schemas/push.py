"""
Pydantic schemas for web push notifications
"""

from pydantic import BaseModel
from typing import Optional


class PushSubscriptionKeys(BaseModel):
    """Keys for push subscription encryption"""
    p256dh: str
    auth: str


class PushSubscriptionRequest(BaseModel):
    """Request to subscribe to push notifications"""
    endpoint: str
    keys: PushSubscriptionKeys
    user_agent: Optional[str] = None


class PushSubscriptionResponse(BaseModel):
    """Response after subscribing"""
    message: str


class VapidPublicKeyResponse(BaseModel):
    """VAPID public key for frontend"""
    public_key: str


class UnsubscribeRequest(BaseModel):
    """Request to unsubscribe from push notifications"""
    endpoint: str
