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


class User(UserBase):
    id: int
    email_verified: bool = False

    class Config:
        from_attributes = True
