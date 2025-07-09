from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime
from bson import ObjectId

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")

class UserStats(BaseModel):
    blogs: int = 0
    upvotes: int = 0
    followers: int = 0
    score: int = 0

class Achievement(BaseModel):
    id: str
    name: str
    description: str
    earned_at: Optional[datetime] = None

class UserBase(BaseModel):
    name: str
    username: str
    email: EmailStr
    bio: Optional[str] = ""
    avatar: Optional[str] = ""

class UserCreate(UserBase):
    clerk_id: str

class UserUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    bio: Optional[str] = None
    avatar: Optional[str] = None

class User(UserBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    clerk_id: str
    stats: UserStats = Field(default_factory=UserStats)
    achievements: List[Achievement] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        schema_extra = {
            "example": {
                "name": "Alex Morgan",
                "username": "alexdesign",
                "email": "alex@example.com",
                "bio": "UI/UX Designer with 10+ years experience",
                "avatar": "https://example.com/avatar.jpg",
                "clerk_id": "user_123456"
            }
        } 