from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Literal
from datetime import datetime
from bson import ObjectId
from .user import PyObjectId

class CommunitySettings(BaseModel):
    """Community settings for features and permissions"""
    enable_member_posts: bool = True
    enable_comments: bool = True
    enable_upvotes: bool = True
    show_members_publicly: bool = True
    require_approval_for_posts: bool = False
    require_approval_for_members: bool = False

class CommunityBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=50)
    description: str = Field(..., min_length=10, max_length=500)
    access_type: Literal['free', 'invite', 'paid'] = 'free'
    price: Optional[float] = None
    categories: List[str] = Field(default_factory=list)
    custom_domain: Optional[str] = None
    settings: CommunitySettings = Field(default_factory=CommunitySettings)

class CommunityCreate(CommunityBase):
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None

class CommunityUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=50)
    description: Optional[str] = Field(None, min_length=10, max_length=500)
    access_type: Optional[Literal['free', 'invite', 'paid']] = None
    price: Optional[float] = None
    categories: Optional[List[str]] = None
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    custom_domain: Optional[str] = None
    settings: Optional[CommunitySettings] = None

class Community(CommunityBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    creator_id: str
    logo_url: Optional[str] = "/placeholder.svg"
    cover_image_url: Optional[str] = "/placeholder.svg"
    member_count: int = 0
    members: List[str] = Field(default_factory=list)
    invite_code: Optional[str] = None  # For invite-only communities
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
    role: Literal['admin', 'moderator', 'member'] = 'member'
    post_count: int = 0
    joined_at: datetime = Field(default_factory=datetime.utcnow)

class CommunityPostAuthor(BaseModel):
    id: str
    name: str
    username: str
    avatar: str

class CommunityPostBase(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    content: str = Field(..., min_length=1)
    type: Literal['discussion', 'announcement', 'question', 'poll', 'link', 'message', 'system'] = 'discussion'
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

class CommunityPostCreate(CommunityPostBase):
    channel_id: Optional[str] = Field(None, description="Channel ID for channel-based posts")
    reply_to: Optional[str] = Field(None, description="ID of message being replied to")

class CommunityPostUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    type: Optional[Literal['discussion', 'announcement', 'question', 'poll', 'link', 'message', 'system']] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None

class CommunityPost(CommunityPostBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    community_id: str
    channel_id: Optional[str] = Field(None, description="Channel ID for channel-based posts")
    author_id: str
    author: Optional[CommunityPostAuthor] = None
    reply_to: Optional[str] = Field(None, description="ID of message being replied to")
    upvotes: int = 0
    upvoted_by: List[str] = Field(default_factory=list)
    comments: int = 0
    is_pinned: bool = False
    is_approved: bool = True  # For communities requiring approval
    is_edited: bool = False
    edited_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

# Enhanced models for real-time messaging
class ChannelPostCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    type: Literal['message', 'announcement', 'system'] = 'message'
    reply_to: Optional[str] = Field(None, description="ID of message being replied to")

class ChannelPostResponse(BaseModel):
    id: str
    content: str
    author: CommunityPostAuthor
    type: str
    channel_id: str
    community_id: str
    reply_to: Optional[str] = None
    created_at: str
    updated_at: str
    is_edited: bool = False
    edited_at: Optional[str] = None

# Real-time event models for SSE
class SSEEventType:
    MESSAGE = "message"
    PRESENCE = "presence"
    USER_JOIN = "user_join"
    USER_LEAVE = "user_leave"
    TYPING = "typing"
    CHANNEL_UPDATE = "channel_update"

class SSEEvent(BaseModel):
    type: str = Field(..., description="Event type")
    data: dict = Field(..., description="Event data")
    community_id: str = Field(..., description="Community ID")
    channel_id: Optional[str] = Field(None, description="Channel ID")
    timestamp: str = Field(..., description="Event timestamp")

class CommunityResponse(BaseModel):
    id: str
    name: str
    description: str
    logo_url: str
    cover_image_url: str
    member_count: int
    access_type: str
    price: Optional[float] = None
    categories: List[str]
    custom_domain: Optional[str] = None
    settings: CommunitySettings
    created_at: str
    is_joined: bool = False
    user_role: Optional[str] = None  # admin, moderator, member

class CommunityPostResponse(BaseModel):
    id: str
    title: Optional[str] = None
    content: str
    author: CommunityPostAuthor
    type: str
    category: Optional[str] = None
    tags: List[str]
    created_at: str
    upvotes: int
    comments: int
    is_upvoted: bool = False
    is_pinned: bool = False

# File upload models for images
class ImageUploadResponse(BaseModel):
    url: str
    filename: str
    size: int
    
class CommunityInvite(BaseModel):
    community_id: str
    invite_code: str
    created_by: str
    expires_at: Optional[datetime] = None
    max_uses: Optional[int] = None
    current_uses: int = 0 