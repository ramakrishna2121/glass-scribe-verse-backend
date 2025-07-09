from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.utils.auth import get_current_user, get_optional_user
from app.database import get_database
from app.models.user import UserUpdate
from app.utils.helpers import convert_objectid_to_str, format_timestamp
from typing import Dict, Any, Optional, List
from datetime import datetime
from bson import ObjectId

router = APIRouter()

@router.get("/profile")
async def get_user_profile(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get current user's profile with stats"""
    db = await get_database()
    
    user = await db.users.find_one({"clerk_id": current_user["clerk_id"]})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Calculate user stats
    blog_count = await db.blogs.count_documents({"author_id": current_user["clerk_id"]})
    total_upvotes = await db.blogs.aggregate([
        {"$match": {"author_id": current_user["clerk_id"]}},
        {"$group": {"_id": None, "total": {"$sum": "$upvotes"}}}
    ]).to_list(1)
    
    upvotes_count = total_upvotes[0]["total"] if total_upvotes else 0
    
    # Update user stats
    await db.users.update_one(
        {"clerk_id": current_user["clerk_id"]},
        {
            "$set": {
                "stats.blogs": blog_count,
                "stats.upvotes": upvotes_count,
                "stats.score": blog_count * 10 + upvotes_count * 5,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    # Get updated user
    updated_user = await db.users.find_one({"clerk_id": current_user["clerk_id"]})
    return convert_objectid_to_str(updated_user)

@router.put("/profile")
async def update_user_profile(
    user_update: UserUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update current user's profile"""
    db = await get_database()
    
    # Check if username is already taken (if being updated)
    if user_update.username:
        existing_user = await db.users.find_one({
            "username": user_update.username,
            "clerk_id": {"$ne": current_user["clerk_id"]}
        })
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
    
    # Update user
    update_data = {k: v for k, v in user_update.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    
    result = await db.users.update_one(
        {"clerk_id": current_user["clerk_id"]},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Return updated user
    updated_user = await db.users.find_one({"clerk_id": current_user["clerk_id"]})
    return convert_objectid_to_str(updated_user)

@router.get("/{user_id}")
async def get_user_by_id(
    user_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """Get user by ID (public endpoint)"""
    db = await get_database()
    
    # Try to find by clerk_id first, then by ObjectId
    user = await db.users.find_one({"clerk_id": user_id})
    
    if not user and ObjectId.is_valid(user_id):
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return convert_objectid_to_str(user)

@router.get("/{user_id}/blogs")
async def get_user_blogs(
    user_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """Get blogs by specific user"""
    db = await get_database()
    
    # Verify user exists
    user = await db.users.find_one({"clerk_id": user_id})
    if not user and ObjectId.is_valid(user_id):
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    skip = (page - 1) * per_page
    
    # Get blogs with author info
    pipeline = [
        {"$match": {"author_id": user["clerk_id"]}},
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
                    "avatar": {"$arrayElemAt": ["$author_info.avatar", 0]},
                    "bio": {"$arrayElemAt": ["$author_info.bio", 0]}
                },
                "timestamp": "$created_at"
            }
        },
        {"$unset": "author_info"}
    ]
    
    blogs = await db.blogs.aggregate(pipeline).to_list(per_page)
    total_count = await db.blogs.count_documents({"author_id": user["clerk_id"]})
    
    # Format timestamps and add upvote status
    for blog in blogs:
        blog["timestamp"] = format_timestamp(blog["timestamp"])
        blog["is_upvoted"] = (
            current_user and current_user["clerk_id"] in blog.get("upvoted_by", [])
        )
    
    return {
        "blogs": convert_objectid_to_str(blogs),
        "total": total_count,
        "page": page,
        "per_page": per_page
    } 