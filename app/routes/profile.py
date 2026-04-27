# backend/app/routes/profile.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from datetime import datetime, timezone  # <-- IMPORT FALTANTE
from bson import ObjectId
from app.utils.auth import get_current_user
from app.models.user import UserResponse
from app.models.profile import UserProfile, UserProfileCreate, UserProfileResponse
from app.database import get_database

router = APIRouter(prefix="/profile", tags=["Perfil Financeiro"])

@router.get("/", response_model=Optional[UserProfileResponse])
async def get_profile(current_user: UserResponse = Depends(get_current_user)):
    db = get_database()
    profile = await db.user_profiles.find_one({"user_id": current_user.id})
    if not profile:
        return None
    profile["_id"] = str(profile["_id"])
    return profile

@router.post("/", response_model=UserProfileResponse)
async def save_profile(
    profile_data: UserProfileCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    db = get_database()
    existing = await db.user_profiles.find_one({"user_id": current_user.id})
    now = datetime.now(timezone.utc)  # <-- AGORA FUNCIONA
    profile_dict = profile_data.model_dump(exclude_unset=True)
    profile_dict["user_id"] = current_user.id
    profile_dict["updated_at"] = now

    if existing:
        await db.user_profiles.update_one(
            {"_id": existing["_id"]},
            {"$set": profile_dict}
        )
        profile_dict["_id"] = str(existing["_id"])
        profile_dict["created_at"] = existing.get("created_at", now)
    else:
        profile_dict["created_at"] = now
        result = await db.user_profiles.insert_one(profile_dict)
        profile_dict["_id"] = str(result.inserted_id)

    return profile_dict