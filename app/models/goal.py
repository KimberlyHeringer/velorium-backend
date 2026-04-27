# app/models/goal.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId

class Goal(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    name: str
    target: float = Field(..., gt=0)
    current: float = Field(default=0, ge=0)
    category: Optional[str] = None
    unit: str = "R$"  # ou '%', etc.
    completed: bool = False
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class GoalCreate(BaseModel):
    name: str
    target: float = Field(..., gt=0)
    current: float = Field(default=0, ge=0)
    category: Optional[str] = None
    unit: str = "R$"

class GoalUpdate(BaseModel):
    name: Optional[str] = None
    target: Optional[float] = Field(None, gt=0)
    current: Optional[float] = Field(None, ge=0)
    category: Optional[str] = None
    unit: Optional[str] = None
    completed: Optional[bool] = None