from fastapi import APIRouter, HTTPException, status, Query, Header
from app.database import get_database
from app.models.community import (
    CommunityCreate, CommunityUpdate, CommunityResponse,
    CommunityPostCreate, CommunityPostUpdate, CommunityPostResponse
)
from app.utils.helpers import convert_objectid_to_str, format_timestamp, sanitize_html
from typing import Optional, List
from datetime import datetime
from bson import ObjectId

router = APIRouter()

# COMMUNITY ENDPOINTS

@router.get("")
async def get_communities(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    access_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None)
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
    
    # Format timestamps
    for community in communities:
        community["created_at"] = format_timestamp(community["created_at"])
    
    return {
        "communities": convert_objectid_to_str(communities),
        "total": total_count,
        "page": page,
        "per_page": per_page
    }

@router.get("/{community_id}")
async def get_community_by_id(community_id: str):
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
    
    return convert_objectid_to_str(community)

@router.post("")
async def create_community(
    community_data: CommunityCreate,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Create a new community (requires user ID from frontend Clerk authentication)"""
    db = await get_database()
    
    # Validate Clerk user ID format
    if not x_user_id or len(x_user_id.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID from header"
        )
    
    # Verify creator exists - try string ID first (Clerk ID), then ObjectId if needed
    creator = await db.users.find_one({"_id": x_user_id})
    if not creator and ObjectId.is_valid(x_user_id):
        creator = await db.users.find_one({"_id": ObjectId(x_user_id)})
    if not creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Please create user profile first."
        )
    
    # Check if community name already exists
    existing_community = await db.communities.find_one({"name": community_data.name})
    if existing_community:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Community name already exists"
        )
    
    community_dict = community_data.dict()
    community_dict["creator_id"] = x_user_id
    community_dict["member_count"] = 1
    community_dict["members"] = [x_user_id]
    community_dict["created_at"] = datetime.utcnow()
    community_dict["updated_at"] = datetime.utcnow()
    
    result = await db.communities.insert_one(community_dict)
    
    # Get the created community
    return await get_community_by_id(str(result.inserted_id))

@router.put("/{community_id}")
async def update_community(
    community_id: str,
    community_update: CommunityUpdate,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Update a community (only by the creator)"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community ID"
        )
    
    if not ObjectId.is_valid(x_user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID from header"
        )
    
    # Check if community exists and user is the creator
    community = await db.communities.find_one({"_id": ObjectId(community_id)})
    
    if not community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found"
        )
    
    if community["creator_id"] != x_user_id:
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
    return await get_community_by_id(community_id)

@router.delete("/{community_id}")
async def delete_community(
    community_id: str,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Delete a community (only by the creator)"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community ID"
        )
    
    if not ObjectId.is_valid(x_user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID from header"
        )
    
    # Check if community exists and user is the creator
    community = await db.communities.find_one({"_id": ObjectId(community_id)})
    
    if not community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found"
        )
    
    if community["creator_id"] != x_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete communities you created"
        )
    
    # Delete community and all its posts
    await db.communities.delete_one({"_id": ObjectId(community_id)})
    await db.community_posts.delete_many({"community_id": community_id})
    
    return {"message": "Community deleted successfully"}

@router.post("/{community_id}/join")
async def join_community(
    community_id: str,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Join a community"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community ID"
        )
    
    if not ObjectId.is_valid(x_user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID from header"
        )
    
    # Verify user exists
    user = await db.users.find_one({"_id": ObjectId(x_user_id)})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if community exists
    community = await db.communities.find_one({"_id": ObjectId(community_id)})
    if not community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found"
        )
    
    # Check if user is already a member
    if x_user_id in community.get("members", []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already a member of this community"
        )
    
    # Add user to community
    await db.communities.update_one(
        {"_id": ObjectId(community_id)},
        {
            "$addToSet": {"members": x_user_id},
            "$inc": {"member_count": 1}
        }
    )
    
    return {"message": "Successfully joined the community"}

@router.post("/{community_id}/leave")
async def leave_community(
    community_id: str,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Leave a community"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community ID"
        )
    
    if not ObjectId.is_valid(x_user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID from header"
        )
    
    # Check if community exists
    community = await db.communities.find_one({"_id": ObjectId(community_id)})
    if not community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found"
        )
    
    # Check if user is a member
    if x_user_id not in community.get("members", []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not a member of this community"
        )
    
    # Prevent creator from leaving
    if community["creator_id"] == x_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Community creator cannot leave. Transfer ownership or delete the community."
        )
    
    # Remove user from community
    await db.communities.update_one(
        {"_id": ObjectId(community_id)},
        {
            "$pull": {"members": x_user_id},
            "$inc": {"member_count": -1}
        }
    )
    
    return {"message": "Successfully left the community"}

@router.get("/{community_id}/members")
async def get_community_members(
    community_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50)
):
    """Get community members"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community ID"
        )
    
    # Check if community exists
    community = await db.communities.find_one({"_id": ObjectId(community_id)})
    if not community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found"
        )
    
    skip = (page - 1) * per_page
    member_ids = community.get("members", [])[skip:skip + per_page]
    
    # Get member details
    if member_ids:
        object_ids = [ObjectId(mid) for mid in member_ids if ObjectId.is_valid(mid)]
        members = await db.users.find({"_id": {"$in": object_ids}}).to_list(per_page)
        
        # Add role information
        for member in members:
            member_id = str(member["_id"])
            member["role"] = "admin" if member_id == community["creator_id"] else "member"
            member["joined_at"] = format_timestamp(community["created_at"])  # Simplified
            member["post_count"] = 0  # You can implement this later
    else:
        members = []
    
    return {
        "members": convert_objectid_to_str(members),
        "total": len(community.get("members", [])),
        "page": page,
        "per_page": per_page
    }

# COMMUNITY POSTS ENDPOINTS

@router.get("/{community_id}/posts")
async def get_community_posts(
    community_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    post_type: Optional[str] = Query(None)
):
    """Get posts in a community"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community ID"
        )
    
    # Check if community exists
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
                "let": {"author_id": {"$toObjectId": "$author_id"}},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$author_id"]}}}
                ],
                "as": "author_info"
            }
        },
        {
            "$addFields": {
                "author": {
                    "id": {"$arrayElemAt": ["$author_info._id", 0]},
                    "name": {"$arrayElemAt": ["$author_info.name", 0]},
                    "username": {"$arrayElemAt": ["$author_info.username", 0]},
                    "avatar": {"$arrayElemAt": ["$author_info.avatar", 0]}
                },
                "created_at": "$created_at"
            }
        },
        {"$unset": "author_info"}
    ]
    
    posts = await db.community_posts.aggregate(pipeline).to_list(per_page)
    total_count = await db.community_posts.count_documents(filter_query)
    
    # Format timestamps
    for post in posts:
        post["created_at"] = format_timestamp(post["created_at"])
    
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
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Create a new post in a community"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community ID"
        )
    
    if not ObjectId.is_valid(x_user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID from header"
        )
    
    # Verify author exists
    author = await db.users.find_one({"_id": ObjectId(x_user_id)})
    if not author:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Please create user profile first."
        )
    
    # Check if community exists
    community = await db.communities.find_one({"_id": ObjectId(community_id)})
    if not community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found"
        )
    
    # Check if user is a member of the community
    if x_user_id not in community.get("members", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be a member of the community to post"
        )
    
    # Sanitize HTML content
    sanitized_content = sanitize_html(post_data.content)
    
    post_dict = post_data.dict()
    post_dict["content"] = sanitized_content
    post_dict["community_id"] = community_id
    post_dict["author_id"] = x_user_id
    post_dict["upvotes"] = 0
    post_dict["upvoted_by"] = []
    post_dict["comments"] = 0
    post_dict["created_at"] = datetime.utcnow()
    post_dict["updated_at"] = datetime.utcnow()
    
    result = await db.community_posts.insert_one(post_dict)
    
    # Get the created post with author info
    created_post = await db.community_posts.find_one({"_id": result.inserted_id})
    
    # Add author info
    created_post["author"] = {
        "id": str(author["_id"]),
        "name": author["name"],
        "username": author["username"],
        "avatar": author.get("avatar", "")
    }
    created_post["created_at"] = format_timestamp(created_post["created_at"])
    
    return convert_objectid_to_str(created_post)

@router.put("/{community_id}/posts/{post_id}")
async def update_community_post(
    community_id: str,
    post_id: str,
    post_update: CommunityPostUpdate,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Update a community post (only by the author)"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community ID"
        )
    
    if not ObjectId.is_valid(post_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid post ID"
        )
    
    if not ObjectId.is_valid(x_user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID from header"
        )
    
    # Check if post exists and user is the author
    post = await db.community_posts.find_one({
        "_id": ObjectId(post_id),
        "community_id": community_id
    })
    
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    
    if post["author_id"] != x_user_id:
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
    
    # Return updated post
    updated_post = await db.community_posts.find_one({"_id": ObjectId(post_id)})
    
    # Add author info
    author = await db.users.find_one({"_id": ObjectId(x_user_id)})
    updated_post["author"] = {
        "id": str(author["_id"]),
        "name": author["name"],
        "username": author["username"],
        "avatar": author.get("avatar", "")
    }
    updated_post["created_at"] = format_timestamp(updated_post["created_at"])
    
    return convert_objectid_to_str(updated_post)

@router.delete("/{community_id}/posts/{post_id}")
async def delete_community_post(
    community_id: str,
    post_id: str,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Delete a community post (only by the author)"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community ID"
        )
    
    if not ObjectId.is_valid(post_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid post ID"
        )
    
    if not ObjectId.is_valid(x_user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID from header"
        )
    
    # Check if post exists and user is the author
    post = await db.community_posts.find_one({
        "_id": ObjectId(post_id),
        "community_id": community_id
    })
    
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    
    if post["author_id"] != x_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own posts"
        )
    
    await db.community_posts.delete_one({"_id": ObjectId(post_id)})
    
    return {"message": "Post deleted successfully"}

@router.post("/{community_id}/posts/{post_id}/upvote")
async def toggle_community_post_upvote(
    community_id: str,
    post_id: str,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Toggle upvote on a community post"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community ID"
        )
    
    if not ObjectId.is_valid(post_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid post ID"
        )
    
    if not ObjectId.is_valid(x_user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID from header"
        )
    
    # Verify user exists
    user = await db.users.find_one({"_id": ObjectId(x_user_id)})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if post exists
    post = await db.community_posts.find_one({
        "_id": ObjectId(post_id),
        "community_id": community_id
    })
    
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    
    # Toggle upvote
    is_upvoted = x_user_id in post.get("upvoted_by", [])
    
    if is_upvoted:
        # Remove upvote
        await db.community_posts.update_one(
            {"_id": ObjectId(post_id)},
            {
                "$pull": {"upvoted_by": x_user_id},
                "$inc": {"upvotes": -1}
            }
        )
        action = "removed"
    else:
        # Add upvote
        await db.community_posts.update_one(
            {"_id": ObjectId(post_id)},
            {
                "$addToSet": {"upvoted_by": x_user_id},
                "$inc": {"upvotes": 1}
            }
        )
        action = "added"
    
    # Get updated post
    updated_post = await db.community_posts.find_one({"_id": ObjectId(post_id)})
    
    return {
        "message": f"Upvote {action} successfully",
        "upvotes": updated_post["upvotes"],
        "is_upvoted": not is_upvoted
    } 