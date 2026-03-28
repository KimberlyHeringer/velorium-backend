from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal
from datetime import datetime, timezone
from decimal import Decimal
from bson import ObjectId

class InstallmentInfo(BaseModel):
    total: int = Field(..., ge=1)
    current: int = Field(1, ge=1)
    start_date: datetime
    due_day: Optional[int] = Field(None, ge=1, le=31)

class NotificationInfo(BaseModel):
    enabled: bool = False
    days_before: int = Field(0, ge=0)

class Bill(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    description: str
    amount: Decimal = Field(..., gt=0)
    installments: InstallmentInfo
    category: Optional[str] = None
    notes: Optional[str] = None
    notification: NotificationInfo = Field(default_factory=NotificationInfo)
    paid: bool = False
    paid_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BillCreate(BaseModel):
    description: str
    amount: Decimal = Field(..., gt=0)
    installments: InstallmentInfo
    category: Optional[str] = None
    notes: Optional[str] = None
    notification: NotificationInfo = Field(default_factory=NotificationInfo)

class BillResponse(BaseModel):
    id: str = Field(..., alias="_id")
    user_id: str
    description: str
    amount: Decimal
    installments: InstallmentInfo
    category: Optional[str]
    notes: Optional[str]
    notification: NotificationInfo
    paid: bool
    paid_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime