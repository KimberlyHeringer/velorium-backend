from datetime import datetime
from pydantic import BaseModel, EmailStr
from typing import Optional

class UserModel:
    def __init__(self, db):
        self.collection = db.users
    
    async def create_user(self, user_data):
        user = {
            "name": user_data.name,
            "email": user_data.email,
            "password_hash": user_data.password,  # Vamos hashear depois
            "monthly_income": user_data.monthly_income,
            "location": user_data.location,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        result = await self.collection.insert_one(user)
        return result.inserted_id
    
    async def get_user_by_email(self, email):
        return await self.collection.find_one({"email": email})