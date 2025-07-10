from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Literal
from datetime import datetime
from bson import ObjectId
from .user import PyObjectId

class CommunityBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=50)
    description: str = Field(..., min_length=10, max_length=500)
    access_type: Literal['free', 'invite', 'paid'] = 'free'
    price: Optional[float] = None
    categories: List[str] = Field(default_factory=list)

class CommunityCreate(CommunityBase):
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None

class CommunityUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=50)
    description: Optional[str] = Field(None, min_length=10, max_length=500)
    access_type: Optional[Literal['free', 'invite', 'paid']] = None
    price: Optional[float] = None
    categories: Optional[List[str]] = None
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None

class Community(CommunityBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    creator_id: str
    logo_url: Optional[str] = "/placeholder.svg"
    banner_url: Optional[str] = "/placeholder.svg"
    member_count: int = 0
    members: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

class CommunityMember(BaseModel):
    id: str
    name: str
    username: str
    avatar: str
    role: Literal['admin', 'member'] = 'member'
    post_count: int = 0
    joined_at: datetime = Field(default_factory=datetime.utcnow)

class CommunityPostAuthor(BaseModel):
    id: str
    name: str
    username: str
    avatar: str

class CommunityPostBase(BaseModel):
    content: str = Field(..., min_length=1)
    type: Literal['blog', 'discussion', 'link', 'image'] = 'discussion'
    category: Optional[str] = None

class CommunityPostCreate(CommunityPostBase):
    pass

class CommunityPostUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1)
    type: Optional[Literal['blog', 'discussion', 'link', 'image']] = None
    category: Optional[str] = None

class CommunityPost(CommunityPostBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    community_id: str
    author_id: str
    author: Optional[CommunityPostAuthor] = None
    upvotes: int = 0
    upvoted_by: List[str] = Field(default_factory=list)
    comments: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

class CommunityResponse(BaseModel):
    id: str
    name: str
    description: str
    logo_url: str
    banner_url: str
    member_count: int
    access_type: str
    price: Optional[float] = None
    created_at: str
    categories: List[str]
    is_joined: bool = False

class CommunityPostResponse(BaseModel):
    id: str
    content: str
    author: CommunityPostAuthor
    type: str
    category: Optional[str] = None
    created_at: str
    upvotes: int
    comments: int
    is_upvoted: bool = False 