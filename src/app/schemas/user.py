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
        json_schema_extra = {
            "example": {
                "role": "Contractor"
            }
        }


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
                "email": "user@example.com"
            }
        }


class User(UserBase):
    id: int
    email_verified: bool = False

    class Config:
        from_attributes = True
