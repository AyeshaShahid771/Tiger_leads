import os
import secrets
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.app import models, schemas
from src.app.api.deps import get_current_user
from src.app.api.endpoints.auth import hash_password
from src.app.core.database import get_db
from src.app.utils.email import send_team_invitation_email
from src.app.utils.team_helpers import get_effective_user_id, is_main_account

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.post(
    "/invite-team-member", response_model=schemas.user.InviteTeamMemberResponse
)
async def invite_team_member(
    request: schemas.user.InviteTeamMemberRequest,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Invite a team member to join your account.

    Only main account holders (not sub-users) can send invitations.
    Invitations are subject to seat limits based on subscription tier.
    """
    # Ensure this action is performed by the main account holder
    main_user_id = get_effective_user_id(current_user)
    if current_user.id != main_user_id or not is_main_account(current_user):
        raise HTTPException(
            status_code=403, detail="Only main account holders can invite team members"
        )

    # Get subscriber info and subscription details
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.user_id == main_user_id)
        .first()
    )

    if not subscriber or not subscriber.subscription_id:
        raise HTTPException(
            status_code=400,
            detail="You must have an active subscription to invite team members",
        )

    # Get subscription to check max_seats
    subscription = (
        db.query(models.user.Subscription)
        .filter(models.user.Subscription.id == subscriber.subscription_id)
        .first()
    )

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    # Check seat availability
    max_seats = subscription.max_seats or 1

    # Free plan (0 seats) cannot invite anyone
    if max_seats == 0:
        raise HTTPException(
            status_code=403,
            detail="Your current plan does not support team members. Please upgrade to add seats.",
        )

    # Use the same logic as my-subscription endpoint
    seats_used = subscriber.seats_used or 0
    purchased_seats = subscriber.purchased_seats or 0
    total_seats = max_seats + purchased_seats
    remaining_seats = max(0, total_seats - seats_used)

    # Check if we have remaining seats
    if remaining_seats <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"You have reached the maximum number of seats ({total_seats}) for your plan. Please upgrade or remove existing team members.",
        )

    # Check if email is already invited or registered
    invited_email = request.email.lower()

    # Check if it's the main user's email
    if invited_email == current_user.email.lower():
        raise HTTPException(status_code=400, detail="You cannot invite yourself")

    # Check if email already exists as a user or sub-user
    existing_user = (
        db.query(models.user.User)
        .filter(models.user.User.email == invited_email)
        .first()
    )

    if existing_user:
        # Do not allow inviting an email that already has an account (main or sub-user)
        raise HTTPException(
            status_code=400,
            detail="Cannot invite: this email already belongs to an existing user on the platform.",
        )

    # Check if already invited
    existing_invitation = (
        db.query(models.user.UserInvitation)
        .filter(
            models.user.UserInvitation.inviter_user_id == main_user_id,
            models.user.UserInvitation.invited_email == invited_email,
            models.user.UserInvitation.status.in_(["pending", "accepted"]),
        )
        .first()
    )

    if existing_invitation:
        status_msg = (
            "already accepted"
            if existing_invitation.status == "accepted"
            else "already pending"
        )
        raise HTTPException(
            status_code=400, detail=f"An invitation to {invited_email} is {status_msg}"
        )

    # Generate permanent invitation token
    invitation_token = secrets.token_urlsafe(32)

    # Create invitation record with user details
    invitation = models.user.UserInvitation(
        inviter_user_id=main_user_id,
        invited_email=invited_email,
        invited_name=request.name,
        invited_phone_number=request.phone_number,
        invited_user_type=request.user_type,
        invitation_token=invitation_token,
        status="pending",
    )

    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    # Update seats_used in subscriber (increment by 1 for the new invitation)
    subscriber.seats_used = seats_used + 1
    db.commit()

    # Send invitation email
    frontend_url = os.getenv("FRONTEND_URL", "https://tigerleads.vercel.app")
    inviter_name = current_user.email  # Could use company name if available

    try:
        email_sent, error_msg = await send_team_invitation_email(
            recipient_email=invited_email,
            inviter_name=inviter_name,
            invitation_token=invitation_token,
            frontend_url=frontend_url,
        )

        if not email_sent:
            # Rollback the invitation if email fails
            db.delete(invitation)
            subscriber.seats_used = seats_used
            db.commit()
            raise HTTPException(
                status_code=500, detail=f"Failed to send invitation email: {error_msg}"
            )
    except HTTPException:
        raise
    except Exception as e:
        # Rollback on any error
        db.delete(invitation)
        subscriber.seats_used = seats_used
        db.commit()
        raise HTTPException(
            status_code=500, detail=f"Failed to send invitation: {str(e)}"
        )

    return {
        "message": "Invitation sent successfully",
        "invited_email": invited_email,
        "invitation_token": invitation_token,
    }


@router.get("/team-members", response_model=schemas.user.TeamMembersListResponse)
def get_team_members(
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get list of all team members and pending invitations.

    Returns the main account info, all sub-users, and pending invitations.
    """
    # Get the main account ID
    main_user_id = get_effective_user_id(current_user)

    # Get main account user
    main_user = (
        db.query(models.user.User).filter(models.user.User.id == main_user_id).first()
    )

    if not main_user:
        raise HTTPException(status_code=404, detail="Main account not found")

    # Get subscriber info for seat counts
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.user_id == main_user_id)
        .first()
    )

    max_seats = 1
    seats_used = 0

    if subscriber and subscriber.subscription_id:
        subscription = (
            db.query(models.user.Subscription)
            .filter(models.user.Subscription.id == subscriber.subscription_id)
            .first()
        )
        if subscription:
            max_seats = subscription.max_seats or 1
            seats_used = subscriber.seats_used or 0

    # Main account info
    # Get main account's profile (Contractor or Supplier)
    main_name = None
    main_phone = None
    main_user_type = None
    
    if main_user.role == "Contractor":
        contractor = (
            db.query(models.user.Contractor)
            .filter(models.user.Contractor.user_id == main_user.id)
            .first()
        )
        if contractor:
            main_name = contractor.primary_contact_name
            main_phone = contractor.phone_number
            main_user_type = contractor.user_type  # Array of user types
    elif main_user.role == "Supplier":
        supplier = (
            db.query(models.user.Supplier)
            .filter(models.user.Supplier.user_id == main_user.id)
            .first()
        )
        if supplier:
            main_name = supplier.primary_contact_name
            main_phone = supplier.phone_number
            main_user_type = supplier.user_type  # Array of user types
    
    main_account_info = schemas.user.TeamMemberResponse(
        id=main_user.id,
        email=main_user.email,
        name=main_name,
        phone_number=main_phone,
        user_type=main_user_type,
        status="active",
        joined_at=main_user.created_at,
        is_main_account=True,
    )

    # Get all sub-users (accepted invitations)
    sub_users = (
        db.query(models.user.User)
        .filter(models.user.User.parent_user_id == main_user_id)
        .all()
    )

    team_members = []

    for sub_user in sub_users:
        # Get sub-user's profile (Contractor or Supplier)
        sub_name = None
        sub_phone = None
        sub_user_type = None
        
        if sub_user.role == "Contractor":
            contractor = (
                db.query(models.user.Contractor)
                .filter(models.user.Contractor.user_id == sub_user.id)
                .first()
            )
            if contractor:
                sub_name = contractor.primary_contact_name
                sub_phone = contractor.phone_number
                sub_user_type = contractor.user_type  # Array of user types
        elif sub_user.role == "Supplier":
            supplier = (
                db.query(models.user.Supplier)
                .filter(models.user.Supplier.user_id == sub_user.id)
                .first()
            )
            if supplier:
                sub_name = supplier.primary_contact_name
                sub_phone = supplier.phone_number
                sub_user_type = supplier.user_type  # Array of user types
        
        team_members.append(
            schemas.user.TeamMemberResponse(
                id=sub_user.id,
                email=sub_user.email,
                name=sub_name,
                phone_number=sub_phone,
                user_type=sub_user_type,
                status="active",
                joined_at=sub_user.created_at,
                is_main_account=False,
            )
        )

    # Get pending invitations
    pending_invitations = (
        db.query(models.user.UserInvitation)
        .filter(
            models.user.UserInvitation.inviter_user_id == main_user_id,
            models.user.UserInvitation.status == "pending",
        )
        .all()
    )

    for invitation in pending_invitations:
        team_members.append(
            schemas.user.TeamMemberResponse(
                id=invitation.id,  # Use invitation ID, not user ID
                email=invitation.invited_email,
                name=invitation.invited_name,  # Get from invitation record
                phone_number=invitation.invited_phone_number,  # Get from invitation record
                user_type=invitation.invited_user_type,  # Get from invitation record
                status="pending",
                joined_at=None,
                is_main_account=False,
            )
        )

    available_seats = max(0, max_seats - seats_used)

    return {
        "main_account": main_account_info,
        "team_members": team_members,
        "seats_used": seats_used,
        "max_seats": max_seats,
        "available_seats": available_seats,
    }


@router.delete("/team-members/{member_id}")
def remove_team_member(
    member_id: int,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Remove a team member or revoke a pending invitation.

    Only main account holders can remove team members.
    You cannot remove yourself (the main account).
    """
    # Only main accounts can remove team members
    if not is_main_account(current_user):
        raise HTTPException(
            status_code=403, detail="Only main account holders can remove team members"
        )

    # Check if this is a pending invitation or an active user
    # First check invitations
    invitation = (
        db.query(models.user.UserInvitation)
        .filter(
            models.user.UserInvitation.id == member_id,
            models.user.UserInvitation.inviter_user_id == current_user.id,
        )
        .first()
    )

    if invitation:
        # Revoke the invitation
        invitation.status = "revoked"
        db.commit()

        # Update seats_used
        subscriber = (
            db.query(models.user.Subscriber)
            .filter(models.user.Subscriber.user_id == current_user.id)
            .first()
        )
        if subscriber and subscriber.seats_used > 0:
            subscriber.seats_used -= 1
            db.commit()

        return {
            "message": "Invitation revoked successfully",
            "email": invitation.invited_email,
        }

    # Check if it's a sub-user
    sub_user = (
        db.query(models.user.User)
        .filter(
            models.user.User.id == member_id,
            models.user.User.parent_user_id == current_user.id,
        )
        .first()
    )

    if not sub_user:
        raise HTTPException(status_code=404, detail="Team member not found")

    # Cannot remove yourself
    if sub_user.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot remove yourself")

    # Delete the sub-user account
    user_email = sub_user.email
    db.delete(sub_user)

    # Update seats_used
    subscriber = (
        db.query(models.user.Subscriber)
        .filter(models.user.Subscriber.user_id == current_user.id)
        .first()
    )
    if subscriber and subscriber.seats_used > 0:
        subscriber.seats_used -= 1

    db.commit()

    return {"message": "Team member removed successfully", "email": user_email}
