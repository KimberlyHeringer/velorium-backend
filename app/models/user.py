# backend/app/models/user.py
from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict
from typing import Optional
from datetime import datetime, timezone
from decimal import Decimal
from bson import ObjectId
import re


class User(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )
    
    id: Optional[str] = Field(None, alias="_id")
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password_hash: str
    monthly_income: Decimal = Field(default=Decimal("0"), ge=0)
    location: str = Field(default="", max_length=200)
    profession_type: str = Field(default="", max_length=50)
    occupation: str = Field(default="", max_length=100)
    financial_goal: str = Field(default="", max_length=500)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)
    monthly_income: Decimal = Field(default=Decimal("0"), ge=0)
    location: str = Field(default="", max_length=200)
    profession_type: str = Field(default="", max_length=50)
    occupation: str = Field(default="", max_length=100)
    financial_goal: str = Field(default="", max_length=500)

    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('A senha deve ter pelo menos 8 caracteres')
        if not re.search(r"[A-Z]", v):
            raise ValueError('A senha deve conter pelo menos uma letra maiúscula')
        if not re.search(r"\d", v):
            raise ValueError('A senha deve conter pelo menos um número')
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError('A senha deve conter pelo menos um caractere especial')
        return v


class UserLogin(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Modelo seguro para respostas - SEM password_hash"""
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )
    
    id: Optional[str] = Field(None, alias="_id")
    name: str
    email: EmailStr
    monthly_income: Decimal
    location: str
    profession_type: str
    occupation: str
    financial_goal: str
    created_at: datetime


class Token(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    
    access_token: str
    token_type: str = "bearer"
    user: UserResponse