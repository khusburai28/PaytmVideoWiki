from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    TEAM_LEAD = "team_lead"
    EMPLOYEE = "employee"


class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: Role = Role.EMPLOYEE


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    team_id: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    user_id: str
    team_id: Optional[str] = None
    team_name: Optional[str] = None
    created_at: datetime
    is_active: bool = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TeamCreate(BaseModel):
    team_name: str
    description: Optional[str] = None


class TeamResponse(BaseModel):
    team_id: str
    team_name: str
    description: Optional[str] = None
    created_by: str
    created_at: datetime
    member_count: int = 0


class AddTeamMemberRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str = Field(..., min_length=8)
    role: Role = Role.EMPLOYEE


class AssignUserToTeamRequest(BaseModel):
    user_id: str
    role: Role = Role.EMPLOYEE


class TeamMemberResponse(BaseModel):
    user_id: str
    email: str
    full_name: str
    role: Role
    joined_at: datetime
