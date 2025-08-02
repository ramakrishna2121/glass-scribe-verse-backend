from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime
from enum import Enum

class PresenceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    AWAY = "away"
    DO_NOT_DISTURB = "dnd"

class PresenceUpdate(BaseModel):
    status: PresenceStatus = Field(..., description="User presence status")
    custom_message: Optional[str] = Field(None, max_length=100, description="Custom status message")
    
    class Config:
        use_enum_values = True

class PresenceResponse(BaseModel):
    user_id: str = Field(..., description="User ID")
    status: PresenceStatus = Field(..., description="User presence status")
    custom_message: Optional[str] = Field(None, description="Custom status message")
    last_seen: str = Field(..., description="Last seen timestamp")
    updated_at: str = Field(..., description="Status update timestamp")
    
    class Config:
        use_enum_values = True

class CommunityPresenceResponse(BaseModel):
    community_id: str = Field(..., description="Community ID")
    presences: Dict[str, PresenceResponse] = Field(..., description="Map of user_id to presence info")
    online_count: int = Field(0, description="Number of online users")
    total_count: int = Field(0, description="Total number of users")

class TypingIndicator(BaseModel):
    user_id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    avatar: Optional[str] = Field(None, description="User avatar URL")
    started_at: str = Field(..., description="When user started typing")

class TypingUpdate(BaseModel):
    typing: bool = Field(..., description="Whether user is typing")

class TypingResponse(BaseModel):
    typing_users: list[TypingIndicator] = Field(default_factory=list, description="List of users currently typing")
    channel_id: str = Field(..., description="Channel ID")
    community_id: str = Field(..., description="Community ID") 