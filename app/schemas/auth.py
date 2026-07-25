from pydantic import BaseModel, EmailStr, Field

from app.schemas.account import AccountWithRole
from app.schemas.user import UserRead


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str
    last_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class MeResponse(UserRead):
    accounts: list[AccountWithRole]
