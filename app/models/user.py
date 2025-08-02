from pydantic import BaseModel, Field, EmailStr, ConfigDict
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema
from typing import Optional, List, Any
from datetime import datetime
from bson import ObjectId

class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler
    ) -> core_schema.CoreSchema:
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.union_schema([
                core_schema.is_instance_schema(ObjectId),
                core_schema.chain_schema([
                    core_schema.str_schema(),
                    core_schema.no_info_plain_validator_function(cls.validate),
                ])
            ]),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda x: str(x)
            ),
        )

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(
        cls, schema: core_schema.CoreSchema, handler
    ) -> JsonSchemaValue:
        return {"type": "string"}

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
    pass

class UserUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    bio: Optional[str] = None
    avatar: Optional[str] = None

class User(UserBase):
    id: str = Field(alias="_id")  # Accept string IDs (Clerk IDs) or ObjectIds
    stats: UserStats = Field(default_factory=UserStats)
    achievements: List[Achievement] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "_id": "user_2NNEqL2nrIRdJ8q3",  # Example Clerk user ID
                "name": "Alex Morgan",
                "username": "alexdesign",
                "email": "alex@example.com",
                "bio": "UI/UX Designer with 10+ years experience",
                "avatar": "https://example.com/avatar.jpg"
            }
        }
    ) 