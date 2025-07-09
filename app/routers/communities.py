from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.utils.auth import get_current_user, get_optional_user
from app.database import get_database
from app.models.community import (
    CommunityCreate, CommunityUpdate, CommunityResponse,
    CommunityPostCreate, CommunityPostUpdate, CommunityPostResponse
)
from app.utils.helpers import convert_objectid_to_str, format_timestamp, sanitize_html
from typing import Dict, Any, Optional, List
from datetime import datetime
from bson import ObjectId

router = APIRouter()

# COMMUNITY ENDPOINTS

@router.get("")
async def get_communities(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    access_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """Get all communities with pagination and filtering"""
    db = await get_database()
    
    # Build filter
    filter_query = {}
    if access_type:
        filter_query["access_type"] = access_type
    if category:
        filter_query["categories"] = {"$in": [category]}
    
    skip = (page - 1) * per_page
    
    communities = await db.communities.find(filter_query)\
        .sort("created_at", -1)\
        .skip(skip)\
        .limit(per_page)\
        .to_list(per_page)
    
    total_count = await db.communities.count_documents(filter_query)
    
    # Add is_joined status for authenticated users
    for community in communities:
        community["created_at"] = format_timestamp(community["created_at"])
        community["is_joined"] = (
            current_user and current_user["clerk_id"] in community.get("members", [])
        )
    
    return {
        "communities": convert_objectid_to_str(communities),
        "total": total_count,
        "page": page,
        "per_page": per_page
    }

@router.get("/{community_id}")
async def get_community_by_id(
    community_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """Get a specific community by ID"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community ID"
        )
    
    community = await db.communities.find_one({"_id": ObjectId(community_id)})
    
    if not community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found"
        )
    
    community["created_at"] = format_timestamp(community["created_at"])
    community["is_joined"] = (
        current_user and current_user["clerk_id"] in community.get("members", [])
    )
    
    return convert_objectid_to_str(community)

@router.post("")
async def create_community(
    community_data: CommunityCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new community"""
    db = await get_database()
    
    # Check if community name already exists
    existing_community = await db.communities.find_one({"name": community_data.name})
    if existing_community:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Community name already exists"
        )
    
    community_dict = community_data.dict()
    community_dict["creator_id"] = current_user["clerk_id"]
    community_dict["member_count"] = 1
    community_dict["members"] = [current_user["clerk_id"]]
    community_dict["created_at"] = datetime.utcnow()
    community_dict["updated_at"] = datetime.utcnow()
    
    result = await db.communities.insert_one(community_dict)
    
    # Get the created community
    created_community = await get_community_by_id(str(result.inserted_id), current_user)
    
    return created_community

@router.put("/{community_id}")
async def update_community(
    community_id: str,
    community_update: CommunityUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update a community (only by the creator)"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community ID"
        )
    
    # Check if community exists and user is the creator
    community = await db.communities.find_one({"_id": ObjectId(community_id)})
    
    if not community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found"
        )
    
    if community["creator_id"] != current_user["clerk_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit communities you created"
        )
    
    # Check if new name already exists (if being updated)
    if community_update.name and community_update.name != community["name"]:
        existing_community = await db.communities.find_one({"name": community_update.name})
        if existing_community:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Community name already exists"
            )
    
    # Update community
    update_data = {k: v for k, v in community_update.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    
    await db.communities.update_one(
        {"_id": ObjectId(community_id)},
        {"$set": update_data}
    )
    
    # Return updated community
    return await get_community_by_id(community_id, current_user)

@router.delete("/{community_id}")
async def delete_community(
    community_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete a community (only by the creator)"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community ID"
        )
    
    # Check if community exists and user is the creator
    community = await db.communities.find_one({"_id": ObjectId(community_id)})
    
    if not community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found"
        )
    
    if community["creator_id"] != current_user["clerk_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete communities you created"
        )
    
    # Delete community and all its posts
    await db.communities.delete_one({"_id": ObjectId(community_id)})
    await db.community_posts.delete_many({"community_id": community_id})
    
    return {"message": "Community deleted successfully"}

# MEMBERSHIP ENDPOINTS

@router.post("/{community_id}/join")
async def join_community(
    community_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Join a community"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community ID"
        )
    
    community = await db.communities.find_one({"_id": ObjectId(community_id)})
    
    if not community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found"
        )
    
    user_id = current_user["clerk_id"]
    
    # Check if user is already a member
    if user_id in community.get("members", []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already a member of this community"
        )
    
    # For paid communities, you might want to check payment status here
    if community["access_type"] == "paid":
        # In a real implementation, you'd integrate with a payment processor
        pass
    
    # Add user to community
    await db.communities.update_one(
        {"_id": ObjectId(community_id)},
        {
            "$addToSet": {"members": user_id},
            "$inc": {"member_count": 1}
        }
    )
    
    return {"message": "Successfully joined the community"}

@router.post("/{community_id}/leave")
async def leave_community(
    community_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Leave a community"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community ID"
        )
    
    community = await db.communities.find_one({"_id": ObjectId(community_id)})
    
    if not community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found"
        )
    
    user_id = current_user["clerk_id"]
    
    # Check if user is a member
    if user_id not in community.get("members", []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not a member of this community"
        )
    
    # Creator cannot leave their own community
    if community["creator_id"] == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Community creators cannot leave their own community"
        )
    
    # Remove user from community
    await db.communities.update_one(
        {"_id": ObjectId(community_id)},
        {
            "$pull": {"members": user_id},
            "$inc": {"member_count": -1}
        }
    )
    
    return {"message": "Successfully left the community"}

@router.get("/{community_id}/members")
async def get_community_members(
    community_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """Get community members"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community ID"
        )
    
    community = await db.communities.find_one({"_id": ObjectId(community_id)})
    
    if not community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found"
        )
    
    member_ids = community.get("members", [])
    skip = (page - 1) * per_page
    
    # Get paginated member info
    members = await db.users.find(
        {"clerk_id": {"$in": member_ids[skip:skip + per_page]}}
    ).to_list(per_page)
    
    # Add role info (creator vs member)
    for member in members:
        member["role"] = "admin" if member["clerk_id"] == community["creator_id"] else "member"
        member["joined_at"] = community["created_at"]  # You might want to track this separately
    
    return {
        "members": convert_objectid_to_str(members),
        "total": len(member_ids),
        "page": page,
        "per_page": per_page
    }

# COMMUNITY POSTS ENDPOINTS

@router.get("/{community_id}/posts")
async def get_community_posts(
    community_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    post_type: Optional[str] = Query(None),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """Get posts in a community"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community ID"
        )
    
    # Verify community exists
    community = await db.communities.find_one({"_id": ObjectId(community_id)})
    if not community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found"
        )
    
    # Build filter
    filter_query = {"community_id": community_id}
    if post_type:
        filter_query["type"] = post_type
    
    skip = (page - 1) * per_page
    
    # Get posts with author info
    pipeline = [
        {"$match": filter_query},
        {"$sort": {"created_at": -1}},
        {"$skip": skip},
        {"$limit": per_page},
        {
            "$lookup": {
                "from": "users",
                "localField": "author_id",
                "foreignField": "clerk_id",
                "as": "author_info"
            }
        },
        {
            "$addFields": {
                "author": {
                    "id": {"$arrayElemAt": ["$author_info.clerk_id", 0]},
                    "name": {"$arrayElemAt": ["$author_info.name", 0]},
                    "username": {"$arrayElemAt": ["$author_info.username", 0]},
                    "avatar": {"$arrayElemAt": ["$author_info.avatar", 0]}
                }
            }
        },
        {"$unset": "author_info"}
    ]
    
    posts = await db.community_posts.aggregate(pipeline).to_list(per_page)
    total_count = await db.community_posts.count_documents(filter_query)
    
    # Format timestamps and add upvote status
    for post in posts:
        post["created_at"] = format_timestamp(post["created_at"])
        post["is_upvoted"] = (
            current_user and current_user["clerk_id"] in post.get("upvoted_by", [])
        )
    
    return {
        "posts": convert_objectid_to_str(posts),
        "total": total_count,
        "page": page,
        "per_page": per_page
    }

@router.post("/{community_id}/posts")
async def create_community_post(
    community_id: str,
    post_data: CommunityPostCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new post in a community"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community ID"
        )
    
    # Verify community exists and user is a member
    community = await db.communities.find_one({"_id": ObjectId(community_id)})
    
    if not community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found"
        )
    
    user_id = current_user["clerk_id"]
    if user_id not in community.get("members", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be a member to post in this community"
        )
    
    # Sanitize content
    sanitized_content = sanitize_html(post_data.content)
    
    post_dict = post_data.dict()
    post_dict["content"] = sanitized_content
    post_dict["community_id"] = community_id
    post_dict["author_id"] = user_id
    post_dict["upvotes"] = 0
    post_dict["upvoted_by"] = []
    post_dict["comments"] = 0
    post_dict["created_at"] = datetime.utcnow()
    post_dict["updated_at"] = datetime.utcnow()
    
    result = await db.community_posts.insert_one(post_dict)
    
    # Get the created post with author info
    created_post = await db.community_posts.aggregate([
        {"$match": {"_id": result.inserted_id}},
        {
            "$lookup": {
                "from": "users",
                "localField": "author_id",
                "foreignField": "clerk_id",
                "as": "author_info"
            }
        },
        {
            "$addFields": {
                "author": {
                    "id": {"$arrayElemAt": ["$author_info.clerk_id", 0]},
                    "name": {"$arrayElemAt": ["$author_info.name", 0]},
                    "username": {"$arrayElemAt": ["$author_info.username", 0]},
                    "avatar": {"$arrayElemAt": ["$author_info.avatar", 0]}
                }
            }
        },
        {"$unset": "author_info"}
    ]).to_list(1)
    
    if created_post:
        post = created_post[0]
        post["created_at"] = format_timestamp(post["created_at"])
        post["is_upvoted"] = False
    
    return convert_objectid_to_str(post)

@router.put("/{community_id}/posts/{post_id}")
async def update_community_post(
    community_id: str,
    post_id: str,
    post_update: CommunityPostUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update a community post (only by the author)"""
    db = await get_database()
    
    if not ObjectId.is_valid(post_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid post ID"
        )
    
    # Check if post exists and user is the author
    post = await db.community_posts.find_one({"_id": ObjectId(post_id)})
    
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    
    if post["author_id"] != current_user["clerk_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own posts"
        )
    
    # Update post
    update_data = {k: v for k, v in post_update.dict().items() if v is not None}
    
    if "content" in update_data:
        update_data["content"] = sanitize_html(update_data["content"])
    
    update_data["updated_at"] = datetime.utcnow()
    
    await db.community_posts.update_one(
        {"_id": ObjectId(post_id)},
        {"$set": update_data}
    )
    
    return {"message": "Post updated successfully"}

@router.delete("/{community_id}/posts/{post_id}")
async def delete_community_post(
    community_id: str,
    post_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete a community post (by author or community creator)"""
    db = await get_database()
    
    if not ObjectId.is_valid(post_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid post ID"
        )
    
    # Check if post exists
    post = await db.community_posts.find_one({"_id": ObjectId(post_id)})
    
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    
    # Check if user can delete (author or community creator)
    community = await db.communities.find_one({"_id": ObjectId(community_id)})
    
    if (post["author_id"] != current_user["clerk_id"] and 
        community and community["creator_id"] != current_user["clerk_id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own posts or posts in communities you created"
        )
    
    await db.community_posts.delete_one({"_id": ObjectId(post_id)})
    
    return {"message": "Post deleted successfully"}

@router.post("/{community_id}/posts/{post_id}/upvote")
async def toggle_community_post_upvote(
    community_id: str,
    post_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Toggle upvote on a community post"""
    db = await get_database()
    
    if not ObjectId.is_valid(post_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid post ID"
        )
    
    post = await db.community_posts.find_one({"_id": ObjectId(post_id)})
    
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    
    user_id = current_user["clerk_id"]
    upvoted_by = post.get("upvoted_by", [])
    
    if user_id in upvoted_by:
        # Remove upvote
        await db.community_posts.update_one(
            {"_id": ObjectId(post_id)},
            {
                "$pull": {"upvoted_by": user_id},
                "$inc": {"upvotes": -1}
            }
        )
        action = "removed"
    else:
        # Add upvote
        await db.community_posts.update_one(
            {"_id": ObjectId(post_id)},
            {
                "$addToSet": {"upvoted_by": user_id},
                "$inc": {"upvotes": 1}
            }
        )
        action = "added"
    
    # Get updated post
    updated_post = await db.community_posts.find_one({"_id": ObjectId(post_id)})
    
    return {
        "message": f"Upvote {action} successfully",
        "upvotes": updated_post["upvotes"],
        "is_upvoted": user_id in updated_post.get("upvoted_by", [])
    } 