from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserLogin(UserBase):
    password: str


class VerifyEmail(BaseModel):
    code: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class RoleUpdate(BaseModel):
    role: str

    class Config:
        json_schema_extra = {"example": {"role": "Contractor"}}


class RoleUpdateResponse(BaseModel):
    message: str
    role: str
    previous_role: str | None = None
    email: EmailStr

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Role updated successfully",
                "role": "Contractor",
                "previous_role": None,
                "email": "user@example.com",
            }
        }


class User(UserBase):
    id: int
    email_verified: bool = False
    parent_user_id: Optional[int] = None

    class Config:
        from_attributes = True


# Team Invitation Schemas
class InviteTeamMemberRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    phone_number: Optional[str] = None
    user_type: Optional[list[str]] = None
    role: str = "viewer"  # viewer or editor
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "john.doe@example.com",
                "name": "John Doe",
                "phone_number": "+1234567890",
                "user_type": ["electrician", "plumber"],
                "role": "editor"
            }
        }
        schema_extra = {
            "description": "Invite a team member to join your account",
            "properties": {
                "email": {
                    "description": "Email address of the team member to invite (required)",
                    "example": "john.doe@example.com"
                },
                "name": {
                    "description": "Full name of the team member (optional)",
                    "example": "John Doe"
                },
                "phone_number": {
                    "description": "Phone number of the team member (optional)",
                    "example": "+1234567890"
                },
                "user_type": {
                    "description": "List of trade types/user types for the team member (optional). Examples: electrician, plumber, hvac, carpenter, etc.",
                    "example": ["electrician", "plumber"]
                },
                "role": {
                    "description": "Access level for the team member: 'viewer' (read-only) or 'editor' (full access like main account). Default: viewer",
                    "example": "editor",
                    "enum": ["viewer", "editor"]
                }
            }
        }


class InviteTeamMemberResponse(BaseModel):
    message: str
    invited_email: str
    invitation_token: str



class TeamMemberResponse(BaseModel):
    id: int
    email: str
    name: Optional[str] = None  # From Contractor/Supplier primary_contact_name
    phone_number: Optional[str] = None  # From Contractor/Supplier phone_number
    user_type: Optional[list[str]] = None  # From Contractor/Supplier user_type array
    status: str  # "active" for accepted users, "pending" for invitations
    joined_at: Optional[datetime] = None
    is_main_account: bool = False
    role: Optional[str] = None  # Team member role: "viewer" or "editor" (only for sub-users)

    class Config:
        from_attributes = True


class TeamMembersListResponse(BaseModel):
    main_account: TeamMemberResponse
    team_members: list[TeamMemberResponse]
    total_seats: int  # Total seats available (subscription + purchased)
    allocated_seats: int  # How many seats are currently used
    available_seats: int  # Remaining seats
    subscription_level: str  # Subscription plan name (e.g., "Free", "Starter", "Pro")


# Admin account update schema (name + optional password change)
class AdminAccountUpdate(BaseModel):
    name: str | None = None
    current_password: str | None = None
    new_password: str | None = None

    class Config:
        json_schema_extra = {
            "example": {"name": "Admin Name", "current_password": "oldpass", "new_password": "newpass"}
        }


# Update team member role schema
class UpdateTeamMemberRoleRequest(BaseModel):
    role: str

    class Config:
        json_schema_extra = {
            "example": {"role": "editor"},
            "json_schema": {
                "properties": {
                    "role": {
                        "description": "New role for the team member: 'viewer' (read-only) or 'editor' (full access)",
                        "example": "editor",
                        "enum": ["viewer", "editor"]
                    }
                }
            }
        }
