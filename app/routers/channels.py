from fastapi import APIRouter, HTTPException, status, Query, Header
from app.database import get_database
from app.models.channel import (
    ChannelCreate, ChannelUpdate, ChannelResponse, ChannelListResponse, 
    ChannelType, ChannelMember
)
from app.models.community import ChannelPostCreate, ChannelPostResponse, CommunityPostAuthor
from app.models.presence import TypingUpdate, TypingResponse, TypingIndicator
from app.utils.helpers import convert_objectid_to_str, format_timestamp
from typing import Optional, List
from datetime import datetime, timedelta
from bson import ObjectId
import secrets

router = APIRouter()

@router.get("/{community_id}/channels")
async def get_community_channels(
    community_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Get all channels in a community"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community ID"
        )
    
    # Check if community exists and user is a member
    community = await db.communities.find_one({"_id": ObjectId(community_id)})
    if not community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found"
        )
    
    if x_user_id not in community.get("members", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be a member to view channels"
        )
    
    skip = (page - 1) * per_page
    
    # Build filter - exclude private channels unless user has access
    filter_query = {"community_id": community_id}
    
    # Get all channels user has access to
    channels = await db.channels.find(filter_query)\
        .sort("created_at", 1)\
        .skip(skip)\
        .limit(per_page)\
        .to_list(per_page)
    
    # Filter out private channels user doesn't have access to
    accessible_channels = []
    for channel in channels:
        if channel.get("is_private", False):
            allowed_users = channel.get("allowed_users", [])
            if x_user_id in allowed_users or channel["created_by"] == x_user_id or community["creator_id"] == x_user_id:
                accessible_channels.append(channel)
        else:
            accessible_channels.append(channel)
    
    total_count = len(accessible_channels)
    
    # Format timestamps and add additional info
    formatted_channels = []
    for channel in accessible_channels:
        # Get member count for this channel
        if channel.get("is_private", False):
            member_count = len(channel.get("allowed_users", []))
        else:
            member_count = len(community.get("members", []))
        
        # Get last message timestamp
        last_message = await db.posts.find_one(
            {"community_id": community_id, "channel_id": str(channel["_id"])},
            sort=[("created_at", -1)]
        )
        
        formatted_channel = ChannelResponse(
            id=str(channel["_id"]),
            name=channel["name"],
            description=channel.get("description"),
            type=channel["type"],
            is_private=channel.get("is_private", False),
            community_id=community_id,
            created_by=channel["created_by"],
            created_at=format_timestamp(channel["created_at"]),
            updated_at=format_timestamp(channel.get("updated_at", channel["created_at"])),
            member_count=member_count,
            last_message_at=format_timestamp(last_message["created_at"]) if last_message else None,
            allowed_users=channel.get("allowed_users", []) if channel.get("is_private", False) else []
        )
        formatted_channels.append(formatted_channel)
    
    return ChannelListResponse(
        channels=formatted_channels,
        total=total_count,
        page=page,
        per_page=per_page
    )

@router.post("/{community_id}/channels")
async def create_channel(
    community_id: str,
    channel_data: ChannelCreate,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Create a new channel in a community"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community ID"
        )
    
    # Check if community exists and user is admin
    community = await db.communities.find_one({"_id": ObjectId(community_id)})
    if not community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found"
        )
    
    # Only community admin can create channels
    if community["creator_id"] != x_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only community admin can create channels"
        )
    
    # Check if channel name already exists in this community
    existing_channel = await db.channels.find_one({
        "community_id": community_id,
        "name": channel_data.name
    })
    if existing_channel:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Channel name already exists in this community"
        )
    
    # Create channel document
    channel_dict = channel_data.dict()
    channel_dict["_id"] = ObjectId()
    channel_dict["community_id"] = community_id
    channel_dict["created_by"] = x_user_id
    channel_dict["created_at"] = datetime.utcnow()
    channel_dict["updated_at"] = datetime.utcnow()
    
    # If private channel but no allowed_users specified, add creator
    if channel_data.is_private and not channel_data.allowed_users:
        channel_dict["allowed_users"] = [x_user_id]
    
    await db.channels.insert_one(channel_dict)
    
    # Return created channel
    return ChannelResponse(
        id=str(channel_dict["_id"]),
        name=channel_dict["name"],
        description=channel_dict.get("description"),
        type=channel_dict["type"],
        is_private=channel_dict.get("is_private", False),
        community_id=community_id,
        created_by=channel_dict["created_by"],
        created_at=format_timestamp(channel_dict["created_at"]),
        updated_at=format_timestamp(channel_dict["updated_at"]),
        member_count=len(channel_dict.get("allowed_users", [])) if channel_dict.get("is_private", False) else len(community.get("members", [])),
        last_message_at=None,
        allowed_users=channel_dict.get("allowed_users", []) if channel_dict.get("is_private", False) else []
    )

@router.put("/{community_id}/channels/{channel_id}")
async def update_channel(
    community_id: str,
    channel_id: str,
    channel_update: ChannelUpdate,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Update a channel (admin only)"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id) or not ObjectId.is_valid(channel_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community or channel ID"
        )
    
    # Check if community exists and user is admin
    community = await db.communities.find_one({"_id": ObjectId(community_id)})
    if not community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found"
        )
    
    if community["creator_id"] != x_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only community admin can update channels"
        )
    
    # Check if channel exists
    channel = await db.channels.find_one({
        "_id": ObjectId(channel_id),
        "community_id": community_id
    })
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )
    
    # Check if new name already exists (if being updated)
    if channel_update.name and channel_update.name != channel["name"]:
        existing_channel = await db.channels.find_one({
            "community_id": community_id,
            "name": channel_update.name,
            "_id": {"$ne": ObjectId(channel_id)}
        })
        if existing_channel:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Channel name already exists in this community"
            )
    
    # Update channel
    update_data = {k: v for k, v in channel_update.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    
    await db.channels.update_one(
        {"_id": ObjectId(channel_id)},
        {"$set": update_data}
    )
    
    # Get updated channel
    updated_channel = await db.channels.find_one({"_id": ObjectId(channel_id)})
    
    return ChannelResponse(
        id=str(updated_channel["_id"]),
        name=updated_channel["name"],
        description=updated_channel.get("description"),
        type=updated_channel["type"],
        is_private=updated_channel.get("is_private", False),
        community_id=community_id,
        created_by=updated_channel["created_by"],
        created_at=format_timestamp(updated_channel["created_at"]),
        updated_at=format_timestamp(updated_channel["updated_at"]),
        member_count=len(updated_channel.get("allowed_users", [])) if updated_channel.get("is_private", False) else len(community.get("members", [])),
        last_message_at=None,
        allowed_users=updated_channel.get("allowed_users", []) if updated_channel.get("is_private", False) else []
    )

@router.delete("/{community_id}/channels/{channel_id}")
async def delete_channel(
    community_id: str,
    channel_id: str,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Delete a channel (admin only)"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id) or not ObjectId.is_valid(channel_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community or channel ID"
        )
    
    # Check if community exists and user is admin
    community = await db.communities.find_one({"_id": ObjectId(community_id)})
    if not community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found"
        )
    
    if community["creator_id"] != x_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only community admin can delete channels"
        )
    
    # Check if channel exists
    channel = await db.channels.find_one({
        "_id": ObjectId(channel_id),
        "community_id": community_id
    })
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )
    
    # Don't allow deleting "general" channel
    if channel["name"].lower() == "general":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the general channel"
        )
    
    # Delete the channel
    await db.channels.delete_one({"_id": ObjectId(channel_id)})
    
    # Delete all messages in this channel
    await db.posts.delete_many({
        "community_id": community_id,
        "channel_id": channel_id
    })
    
    return {"message": "Channel deleted successfully"}

# Initialize default channels for new communities
async def create_default_channels(db, community_id: str, creator_id: str):
    """Create default channels for a new community"""
    default_channels = [
        {
            "name": "general",
            "description": "General discussions",
            "type": ChannelType.GENERAL,
            "is_private": False
        },
        {
            "name": "announcements",
            "description": "Important announcements",
            "type": ChannelType.ANNOUNCEMENT,
            "is_private": False
        }
    ]
    
    for channel_data in default_channels:
        channel_doc = {
            "_id": ObjectId(),
            "community_id": community_id,
            "created_by": creator_id,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            **channel_data
        }
        await db.channels.insert_one(channel_doc)

# CHANNEL MESSAGING ENDPOINTS

@router.get("/{community_id}/channels/{channel_id}/posts")
async def get_channel_messages(
    community_id: str,
    channel_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    before: Optional[str] = Query(None, description="Get messages before this message ID"),
    after: Optional[str] = Query(None, description="Get messages after this message ID"),
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Get messages in a specific channel"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community ID"
        )
    
    # Check if community exists and user is a member
    community = await db.communities.find_one({"_id": ObjectId(community_id)})
    if not community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found"
        )
    
    if x_user_id not in community.get("members", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be a member to view messages"
        )
    
    # Check if channel exists and user has access
    if ObjectId.is_valid(channel_id):
        channel = await db.channels.find_one({
            "_id": ObjectId(channel_id),
            "community_id": community_id
        })
    else:
        channel = await db.channels.find_one({
            "community_id": community_id,
            "$or": [
                {"_id": channel_id},
                {"name": channel_id}
            ]
        })
    
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )
    
    # Check access to private channels
    if channel.get("is_private", False):
        allowed_users = channel.get("allowed_users", [])
        if x_user_id not in allowed_users and channel["created_by"] != x_user_id and community["creator_id"] != x_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this private channel"
            )
    
    # Build filter for messages
    filter_query = {
        "community_id": community_id,
        "channel_id": str(channel["_id"]),
        "type": {"$in": ["message", "announcement", "system"]}
    }
    
    # Add before/after filters
    if before and ObjectId.is_valid(before):
        filter_query["_id"] = {"$lt": ObjectId(before)}
    elif after and ObjectId.is_valid(after):
        filter_query["_id"] = {"$gt": ObjectId(after)}
    
    skip = (page - 1) * per_page
    
    # Get messages
    messages = await db.posts.find(filter_query)\
        .sort("created_at", -1)\
        .skip(skip)\
        .limit(per_page)\
        .to_list(per_page)
    
    total_count = await db.posts.count_documents(filter_query)
    
    # Get author information for each message
    formatted_messages = []
    for message in messages:
        # Get author info
        author = await db.users.find_one({"_id": message["author_id"]})
        if author:
            author_info = CommunityPostAuthor(
                id=str(author["_id"]),
                name=author["name"],
                username=author.get("username", ""),
                avatar=author.get("avatar", "")
            )
        else:
            author_info = CommunityPostAuthor(
                id=message["author_id"],
                name="Unknown User",
                username="unknown",
                avatar=""
            )
        
        formatted_message = ChannelPostResponse(
            id=str(message["_id"]),
            content=message["content"],
            author=author_info,
            type=message["type"],
            channel_id=str(channel["_id"]),
            community_id=community_id,
            reply_to=message.get("reply_to"),
            created_at=format_timestamp(message["created_at"]),
            updated_at=format_timestamp(message.get("updated_at", message["created_at"])),
            is_edited=message.get("is_edited", False),
            edited_at=format_timestamp(message["edited_at"]) if message.get("edited_at") else None
        )
        formatted_messages.append(formatted_message)
    
    return {
        "messages": formatted_messages,
        "total": total_count,
        "page": page,
        "per_page": per_page,
        "channel": {
            "id": str(channel["_id"]),
            "name": channel["name"],
            "type": channel["type"]
        }
    }

@router.post("/{community_id}/channels/{channel_id}/posts")
async def create_channel_message(
    community_id: str,
    channel_id: str,
    message_data: ChannelPostCreate,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Send a message to a specific channel"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community ID"
        )
    
    # Check if community exists and user is a member
    community = await db.communities.find_one({"_id": ObjectId(community_id)})
    if not community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found"
        )
    
    if x_user_id not in community.get("members", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be a member to send messages"
        )
    
    # Check if channel exists and user has access
    if ObjectId.is_valid(channel_id):
        channel = await db.channels.find_one({
            "_id": ObjectId(channel_id),
            "community_id": community_id
        })
    else:
        channel = await db.channels.find_one({
            "community_id": community_id,
            "$or": [
                {"_id": channel_id},
                {"name": channel_id}
            ]
        })
    
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )
    
    # Check access to private channels
    if channel.get("is_private", False):
        allowed_users = channel.get("allowed_users", [])
        if x_user_id not in allowed_users and channel["created_by"] != x_user_id and community["creator_id"] != x_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this private channel"
            )
    
    # Check permissions for announcement channels
    if channel["type"] == ChannelType.ANNOUNCEMENT and message_data.type == "announcement":
        if community["creator_id"] != x_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only community admin can post announcements"
            )
    
    # Verify user exists
    user = await db.users.find_one({"_id": x_user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Create message document
    message_dict = message_data.dict()
    message_dict["_id"] = ObjectId()
    message_dict["community_id"] = community_id
    message_dict["channel_id"] = str(channel["_id"])
    message_dict["author_id"] = x_user_id
    message_dict["title"] = None  # Channel messages don't have titles
    message_dict["category"] = None
    message_dict["tags"] = []
    message_dict["upvotes"] = 0
    message_dict["upvoted_by"] = []
    message_dict["comments"] = 0
    message_dict["is_pinned"] = False
    message_dict["is_approved"] = True
    message_dict["is_edited"] = False
    message_dict["created_at"] = datetime.utcnow()
    message_dict["updated_at"] = datetime.utcnow()
    
    await db.posts.insert_one(message_dict)
    
    # Get author info for response
    author_info = CommunityPostAuthor(
        id=str(user["_id"]),
        name=user["name"],
        username=user.get("username", ""),
        avatar=user.get("avatar", "")
    )
    
    # Return created message
    return ChannelPostResponse(
        id=str(message_dict["_id"]),
        content=message_dict["content"],
        author=author_info,
        type=message_dict["type"],
        channel_id=str(channel["_id"]),
        community_id=community_id,
        reply_to=message_dict.get("reply_to"),
        created_at=format_timestamp(message_dict["created_at"]),
        updated_at=format_timestamp(message_dict["updated_at"]),
        is_edited=False,
        edited_at=None
    )

# TYPING INDICATORS

@router.post("/{community_id}/channels/{channel_id}/typing")
async def send_typing_indicator(
    community_id: str,
    channel_id: str,
    typing_data: TypingUpdate,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Send typing indicator for a channel"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community ID"
        )
    
    # Check if community exists and user is a member
    community = await db.communities.find_one({"_id": ObjectId(community_id)})
    if not community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found"
        )
    
    if x_user_id not in community.get("members", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be a member to send typing indicators"
        )
    
    # Check if channel exists
    if ObjectId.is_valid(channel_id):
        channel = await db.channels.find_one({
            "_id": ObjectId(channel_id),
            "community_id": community_id
        })
    else:
        channel = await db.channels.find_one({
            "community_id": community_id,
            "$or": [
                {"_id": channel_id},
                {"name": channel_id}
            ]
        })
    
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )
    
    # Get user info
    user = await db.users.find_one({"_id": x_user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    channel_id_str = str(channel["_id"])
    
    if typing_data.typing:
        # Add or update typing indicator
        typing_doc = {
            "user_id": x_user_id,
            "username": user.get("username", user["name"]),
            "avatar": user.get("avatar"),
            "community_id": community_id,
            "channel_id": channel_id_str,
            "started_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(seconds=3)
        }
        
        await db.typing_indicators.update_one(
            {
                "user_id": x_user_id,
                "community_id": community_id,
                "channel_id": channel_id_str
            },
            {"$set": typing_doc},
            upsert=True
        )
    else:
        # Remove typing indicator
        await db.typing_indicators.delete_one({
            "user_id": x_user_id,
            "community_id": community_id,
            "channel_id": channel_id_str
        })
    
    return {"success": True}

@router.get("/{community_id}/channels/{channel_id}/typing")
async def get_typing_indicators(
    community_id: str,
    channel_id: str,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Get current typing indicators for a channel"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community ID"
        )
    
    # Check if community exists and user is a member
    community = await db.communities.find_one({"_id": ObjectId(community_id)})
    if not community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found"
        )
    
    if x_user_id not in community.get("members", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be a member to view typing indicators"
        )
    
    # Check if channel exists
    if ObjectId.is_valid(channel_id):
        channel = await db.channels.find_one({
            "_id": ObjectId(channel_id),
            "community_id": community_id
        })
    else:
        channel = await db.channels.find_one({
            "community_id": community_id,
            "$or": [
                {"_id": channel_id},
                {"name": channel_id}
            ]
        })
    
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )
    
    channel_id_str = str(channel["_id"])
    
    # Clean up expired typing indicators
    await db.typing_indicators.delete_many({
        "expires_at": {"$lt": datetime.utcnow()}
    })
    
    # Get current typing indicators (excluding current user)
    typing_indicators = await db.typing_indicators.find({
        "community_id": community_id,
        "channel_id": channel_id_str,
        "user_id": {"$ne": x_user_id}
    }).to_list(None)
    
    # Format response
    typing_users = []
    for indicator in typing_indicators:
        typing_user = TypingIndicator(
            user_id=indicator["user_id"],
            username=indicator["username"],
            avatar=indicator.get("avatar"),
            started_at=format_timestamp(indicator["started_at"])
        )
        typing_users.append(typing_user)
    
    return TypingResponse(
        typing_users=typing_users,
        channel_id=channel_id_str,
        community_id=community_id
    ) 