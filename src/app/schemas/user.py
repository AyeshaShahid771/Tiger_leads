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


class InviteTeamMemberResponse(BaseModel):
    message: str
    invited_email: str
    invitation_token: str


class TeamMemberResponse(BaseModel):
    id: int
    email: str
    status: str  # "active" for accepted users, "pending" for invitations
    joined_at: Optional[datetime] = None
    is_main_account: bool = False

    class Config:
        from_attributes = True


class TeamMembersListResponse(BaseModel):
    main_account: TeamMemberResponse
    team_members: list[TeamMemberResponse]
    seats_used: int
    max_seats: int
    available_seats: int
