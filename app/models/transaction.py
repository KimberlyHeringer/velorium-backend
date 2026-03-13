# backend/app/models/transaction.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal
from datetime import datetime, timezone
from decimal import Decimal
from bson import ObjectId


class Transaction(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    type: Literal["income", "expense"]
    amount: Decimal = Field(..., gt=0)
    category: str
    description: Optional[str] = None
    date: datetime
    payment_method: Optional[str] = None
    context: Literal["individual", "familia", "profissional"]
    family_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TransactionCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    type: Literal["income", "expense"]
    amount: Decimal = Field(..., gt=0)
    category: str
    description: Optional[str] = None
    date: Optional[datetime] = None
    payment_method: Optional[str] = None
    context: Literal["individual", "familia", "profissional"] = "individual"
    family_id: Optional[str] = None


class TransactionUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    type: Optional[Literal["income", "expense"]] = None
    amount: Optional[Decimal] = Field(None, gt=0)
    category: Optional[str] = None
    description: Optional[str] = None
    date: Optional[datetime] = None
    payment_method: Optional[str] = None
    context: Optional[Literal["individual", "familia", "profissional"]] = None
    family_id: Optional[str] = None


class TransactionResponse(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )
    id: str = Field(..., alias="_id")
    user_id: str
    type: str
    amount: Decimal
    category: str
    description: Optional[str]
    date: datetime
    payment_method: Optional[str]
    context: str
    family_id: Optional[str]
    created_at: datetime
    updated_at: datetime


class TransactionBalance(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    income: Decimal
    expense: Decimal
    balance: Decimal
    context: Optional[str] = None