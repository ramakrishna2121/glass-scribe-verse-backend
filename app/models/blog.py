from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from bson import ObjectId
from .user import PyObjectId

class Author(BaseModel):
    id: str
    name: str
    username: str
    avatar: str
    bio: str

class BlogBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    excerpt: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    category: str

class BlogCreate(BlogBase):
    pass

class BlogUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    excerpt: Optional[str] = Field(None, min_length=1, max_length=500)
    content: Optional[str] = Field(None, min_length=1)
    category: Optional[str] = None

class Blog(BlogBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    author_id: str
    author: Optional[Author] = None
    upvotes: int = 0
    upvoted_by: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        schema_extra = {
            "example": {
                "title": "The Art of Minimalist Design",
                "excerpt": "Exploring how less becomes more in modern UI/UX design philosophy.",
                "content": "<p>Minimalism in design isn't just about using fewer elements...</p>",
                "category": "Design",
                "author_id": "user_123456"
            }
        }

class BlogResponse(BaseModel):
    id: str
    title: str
    excerpt: str
    content: str
    category: str
    author: Author
    upvotes: int
    timestamp: str
    is_upvoted: bool = False

    class Config:
        schema_extra = {
            "example": {
                "id": "64a7b8c9d1e2f3a4b5c6d7e8",
                "title": "The Art of Minimalist Design",
                "excerpt": "Exploring how less becomes more in modern UI/UX design philosophy.",
                "content": "<p>Minimalism in design isn't just about using fewer elements...</p>",
                "category": "Design",
                "author": {
                    "id": "user_123456",
                    "name": "Alex Morgan",
                    "username": "alexdesign",
                    "avatar": "https://example.com/avatar.jpg",
                    "bio": "UI/UX Designer with 10+ years experience"
                },
                "upvotes": 128,
                "timestamp": "2 days ago",
                "is_upvoted": False
            }
        } 