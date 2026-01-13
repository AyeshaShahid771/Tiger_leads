"""
Add-on Management Endpoints

These endpoints handle the subscription add-on system:
- Stay Active Bonus (30 credits) - Available in all tiers
- Bonus Credits (50 credits) - Available in Professional & Enterprise
- Boost Pack (100 credits + 1 seat) - Available in Professional only
"""

# Add these imports to subscription.py if not already present
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from src.app import models
from src.app.api.deps import get_current_user, get_effective_user
from src.app.core.database import get_db

# Add to existing router in subscription.py

@router.get("/my-add-ons")
def get_my_add_ons(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Get available add-ons for the current user's subscription tier.
    
    Returns earned but unredeemed add-ons and their availability based on tier.
    
    Response includes:
    - Which add-ons are available for current tier
    - How many credits/seats are earned but not yet redeemed
    - Last redemption timestamps
    """
    # Get subscriber information
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.user_id == effective_user.id)
        .first()
    )
    
    if not subscriber:
        raise HTTPException(
            status_code=404,
            detail="No subscription found. Please subscribe to a plan first."
        )
    
    # Get subscription plan to check tier and available add-ons
    subscription = None
    if subscriber.subscription_id:
        subscription = (
            db.query(models.user.Subscription)
            .filter(models.user.Subscription.id == subscriber.subscription_id)
            .first()
        )
    
    if not subscription:
        return {
            "message": "No active subscription plan",
            "stay_active_bonus": {
                "available": False,
                "credits_earned": 0,
                "last_redeemed": None
            },
            "bonus_credits": {
                "available": False,
                "credits_earned": 0,
                "last_redeemed": None
            },
            "boost_pack": {
                "available": False,
                "credits_earned": 0,
                "seats_earned": 0,
                "last_redeemed": None
            }
        }
    
    return {
        "subscription_tier": subscription.name,
        "tier_level": subscription.tier_level,
        "stay_active_bonus": {
            "available": subscription.has_stay_active_bonus,
            "credits_earned": subscriber.stay_active_credits or 0,
            "credit_value": 30,  # Stay Active = 30 credits
            "last_redeemed": subscriber.last_stay_active_redemption.isoformat() if subscriber.last_stay_active_redemption else None
        },
        "bonus_credits": {
            "available": subscription.has_bonus_credits,
            "credits_earned": subscriber.bonus_credits or 0,
            "credit_value": 50,  # Bonus Credits = 50 credits
            "last_redeemed": subscriber.last_bonus_redemption.isoformat() if subscriber.last_bonus_redemption else None
        },
        "boost_pack": {
            "available": subscription.has_boost_pack,
            "credits_earned": subscriber.boost_pack_credits or 0,
            "seats_earned": subscriber.boost_pack_seats or 0,
            "credit_value": 100,  # Boost Pack = 100 credits
            "seat_value": 1,  # Boost Pack = 1 seat
            "last_redeemed": subscriber.last_boost_redemption.isoformat() if subscriber.last_boost_redemption else None
        }
    }


@router.post("/redeem-add-on")
def redeem_add_on(
    add_on_type: str = Body(..., embed=True, description="stay_active_bonus | bonus_credits | boost_pack"),
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    """
    Redeem an earned add-on to convert it to active credits/seats.
    
    Parameters:
    - add_on_type: Type of add-on to redeem
      * "stay_active_bonus" - 30 credits
      * "bonus_credits" - 50 credits
      * "boost_pack" - 100 credits + 1 seat
    
    Process:
    1. Validates add-on is available for user's tier
    2. Checks user has earned credits/seats
    3. Adds to current_credits and seats
    4. Resets earned amount to 0
    5. Updates redemption timestamp
    """
    # Validate add_on_type
    valid_types = ["stay_active_bonus", "bonus_credits", "boost_pack"]
    if add_on_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid add_on_type. Must be one of: {', '.join(valid_types)}"
        )
    
    # Get subscriber
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.user_id == effective_user.id)
        .first()
    )
    
    if not subscriber:
        raise HTTPException(
            status_code=404,
            detail="No subscription found. Please subscribe to a plan first."
        )
    
    # Get subscription to check availability
    subscription = None
    if subscriber.subscription_id:
        subscription = (
            db.query(models.user.Subscription)
            .filter(models.user.Subscription.id == subscriber.subscription_id)
            .first()
        )
    
    if not subscription:
        raise HTTPException(
            status_code=403,
            detail="No active subscription plan. Please subscribe first."
        )
    
    # Check if add-on is available for this tier
    if add_on_type == "stay_active_bonus":
        if not subscription.has_stay_active_bonus:
            raise HTTPException(
                status_code=403,
                detail="Stay Active Bonus not available for your subscription tier"
            )
        earned_credits = subscriber.stay_active_credits or 0
        if earned_credits == 0:
            raise HTTPException(
                status_code=400,
                detail="No Stay Active Bonus credits earned. Earn 30 credits first."
            )
        
        # Redeem credits
        subscriber.current_credits += earned_credits
        subscriber.stay_active_credits = 0
        subscriber.last_stay_active_redemption = datetime.utcnow()
        
        db.commit()
        db.refresh(subscriber)
        
        return {
            "message": "Stay Active Bonus redeemed successfully",
            "credits_added": earned_credits,
            "new_credit_balance": subscriber.current_credits,
            "redeemed_at": subscriber.last_stay_active_redemption.isoformat()
        }
    
    elif add_on_type == "bonus_credits":
        if not subscription.has_bonus_credits:
            raise HTTPException(
                status_code=403,
                detail="Bonus Credits not available for your subscription tier"
            )
        earned_credits = subscriber.bonus_credits or 0
        if earned_credits == 0:
            raise HTTPException(
                status_code=400,
                detail="No Bonus Credits earned. Earn 50 credits first."
            )
        
        # Redeem credits
        subscriber.current_credits += earned_credits
        subscriber.bonus_credits = 0
        subscriber.last_bonus_redemption = datetime.utcnow()
        
        db.commit()
        db.refresh(subscriber)
        
        return {
            "message": "Bonus Credits redeemed successfully",
            "credits_added": earned_credits,
            "new_credit_balance": subscriber.current_credits,
            "redeemed_at": subscriber.last_bonus_redemption.isoformat()
        }
    
    elif add_on_type == "boost_pack":
        if not subscription.has_boost_pack:
            raise HTTPException(
                status_code=403,
                detail="Boost Pack not available for your subscription tier (Professional only)"
            )
        earned_credits = subscriber.boost_pack_credits or 0
        earned_seats = subscriber.boost_pack_seats or 0
        
        if earned_credits == 0 and earned_seats == 0:
            raise HTTPException(
                status_code=400,
                detail="No Boost Pack earned. Earn 100 credits + 1 seat first."
            )
        
        # Redeem credits and seats
        subscriber.current_credits += earned_credits
        # Note: Seats are managed separately - this just tracks the boost pack seat allocation
        # You may need to update max_seats in subscription logic
        subscriber.boost_pack_credits = 0
        subscriber.boost_pack_seats = 0
        subscriber.last_boost_redemption = datetime.utcnow()
        
        db.commit()
        db.refresh(subscriber)
        
        return {
            "message": "Boost Pack redeemed successfully",
            "credits_added": earned_credits,
            "seats_added": earned_seats,
            "new_credit_balance": subscriber.current_credits,
            "redeemed_at": subscriber.last_boost_redemption.isoformat(),
            "note": "Contact support to activate your additional seat"
        }


@router.post("/admin/grant-add-on", dependencies=[Depends(require_admin_token)])
def admin_grant_add_on(
    user_id: int = Body(...),
    add_on_type: str = Body(..., description="stay_active_bonus | bonus_credits | boost_pack"),
    credits: int = Body(None, description="Override credit amount (optional)"),
    seats: int = Body(None, description="Override seat amount for boost_pack (optional)"),
    db: Session = Depends(get_db),
):
    """
    Admin endpoint to manually grant add-ons to users.
    
    Parameters:
    - user_id: ID of the user to grant add-on to
    - add_on_type: Type of add-on to grant
    - credits: Optional credit amount override (defaults: 30, 50, or 100)
    - seats: Optional seat amount for boost_pack (default: 1)
    
    This grants the add-on credits/seats without redeeming them immediately.
    User must call /redeem-add-on to convert to active credits/seats.
    """
    # Validate add_on_type
    valid_types = ["stay_active_bonus", "bonus_credits", "boost_pack"]
    if add_on_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid add_on_type. Must be one of: {', '.join(valid_types)}"
        )
    
    # Get subscriber
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.user_id == user_id)
        .first()
    )
    
    if not subscriber:
        raise HTTPException(
            status_code=404,
            detail=f"No subscriber found for user_id {user_id}"
        )
    
    # Set default credit amounts if not specified
    if add_on_type == "stay_active_bonus":
        credit_amount = credits if credits is not None else 30
        subscriber.stay_active_credits = (subscriber.stay_active_credits or 0) + credit_amount
        
        db.commit()
        
        return {
            "message": f"Granted {credit_amount} Stay Active Bonus credits to user {user_id}",
            "user_id": user_id,
            "add_on_type": add_on_type,
            "credits_granted": credit_amount,
            "total_stay_active_credits": subscriber.stay_active_credits
        }
    
    elif add_on_type == "bonus_credits":
        credit_amount = credits if credits is not None else 50
        subscriber.bonus_credits = (subscriber.bonus_credits or 0) + credit_amount
        
        db.commit()
        
        return {
            "message": f"Granted {credit_amount} Bonus Credits to user {user_id}",
            "user_id": user_id,
            "add_on_type": add_on_type,
            "credits_granted": credit_amount,
            "total_bonus_credits": subscriber.bonus_credits
        }
    
    elif add_on_type == "boost_pack":
        credit_amount = credits if credits is not None else 100
        seat_amount = seats if seats is not None else 1
        
        subscriber.boost_pack_credits = (subscriber.boost_pack_credits or 0) + credit_amount
        subscriber.boost_pack_seats = (subscriber.boost_pack_seats or 0) + seat_amount
        
        db.commit()
        
        return {
            "message": f"Granted Boost Pack ({credit_amount} credits + {seat_amount} seat) to user {user_id}",
            "user_id": user_id,
            "add_on_type": add_on_type,
            "credits_granted": credit_amount,
            "seats_granted": seat_amount,
            "total_boost_pack_credits": subscriber.boost_pack_credits,
            "total_boost_pack_seats": subscriber.boost_pack_seats
        }
