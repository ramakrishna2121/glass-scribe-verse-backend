from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class ChannelType(str, Enum):
    TEXT = "text"
    ANNOUNCEMENT = "announcement"
    GENERAL = "general"
    VOICE = "voice"

class ChannelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Channel name")
    description: Optional[str] = Field(None, max_length=500, description="Channel description")
    type: ChannelType = Field(ChannelType.TEXT, description="Channel type")
    is_private: bool = Field(False, description="Whether the channel is private")
    allowed_users: Optional[List[str]] = Field(default_factory=list, description="List of user IDs allowed in private channels")
    
    class Config:
        use_enum_values = True

class ChannelUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Channel name")
    description: Optional[str] = Field(None, max_length=500, description="Channel description")
    type: Optional[ChannelType] = Field(None, description="Channel type")
    is_private: Optional[bool] = Field(None, description="Whether the channel is private")
    allowed_users: Optional[List[str]] = Field(None, description="List of user IDs allowed in private channels")
    
    class Config:
        use_enum_values = True

class ChannelResponse(BaseModel):
    id: str = Field(..., description="Channel ID")
    name: str = Field(..., description="Channel name")
    description: Optional[str] = Field(None, description="Channel description")
    type: ChannelType = Field(..., description="Channel type")
    is_private: bool = Field(..., description="Whether the channel is private")
    community_id: str = Field(..., description="ID of the community this channel belongs to")
    created_by: str = Field(..., description="User ID who created the channel")
    created_at: str = Field(..., description="Channel creation timestamp")
    updated_at: str = Field(..., description="Channel last update timestamp")
    member_count: int = Field(0, description="Number of members in the channel")
    last_message_at: Optional[str] = Field(None, description="Timestamp of last message in channel")
    allowed_users: Optional[List[str]] = Field(default_factory=list, description="List of user IDs allowed in private channels")
    
    class Config:
        use_enum_values = True

class ChannelMember(BaseModel):
    user_id: str = Field(..., description="User ID")
    joined_at: str = Field(..., description="When user joined the channel")
    role: Optional[str] = Field("member", description="User role in channel")

class ChannelListResponse(BaseModel):
    channels: List[ChannelResponse] = Field(..., description="List of channels")
    total: int = Field(..., description="Total number of channels")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Items per page") 