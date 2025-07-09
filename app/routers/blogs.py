from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.utils.auth import get_current_user, get_optional_user
from app.database import get_database
from app.models.blog import BlogCreate, BlogUpdate, BlogResponse
from app.utils.helpers import convert_objectid_to_str, format_timestamp, sanitize_html
from typing import Dict, Any, Optional, List
from datetime import datetime
from bson import ObjectId

router = APIRouter()

@router.get("")
async def get_blogs(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    category: Optional[str] = Query(None),
    author: Optional[str] = Query(None),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """Get all blogs with pagination and filtering"""
    db = await get_database()
    
    # Build filter
    filter_query = {}
    if category:
        filter_query["category"] = category
    if author:
        filter_query["author_id"] = author
    
    skip = (page - 1) * per_page
    
    # Get blogs with author info
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
                    "avatar": {"$arrayElemAt": ["$author_info.avatar", 0]},
                    "bio": {"$arrayElemAt": ["$author_info.bio", 0]}
                },
                "timestamp": "$created_at"
            }
        },
        {"$unset": "author_info"}
    ]
    
    blogs = await db.blogs.aggregate(pipeline).to_list(per_page)
    total_count = await db.blogs.count_documents(filter_query)
    
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

@router.get("/search")
async def search_blogs(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """Search blogs by title, content, category, or author"""
    db = await get_database()
    
    skip = (page - 1) * per_page
    
    # Create text search pipeline
    pipeline = [
        {
            "$match": {
                "$or": [
                    {"title": {"$regex": q, "$options": "i"}},
                    {"content": {"$regex": q, "$options": "i"}},
                    {"category": {"$regex": q, "$options": "i"}},
                    {"excerpt": {"$regex": q, "$options": "i"}}
                ]
            }
        },
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
    
    # Count total matching documents
    count_pipeline = [
        {
            "$match": {
                "$or": [
                    {"title": {"$regex": q, "$options": "i"}},
                    {"content": {"$regex": q, "$options": "i"}},
                    {"category": {"$regex": q, "$options": "i"}},
                    {"excerpt": {"$regex": q, "$options": "i"}}
                ]
            }
        },
        {"$count": "total"}
    ]
    
    count_result = await db.blogs.aggregate(count_pipeline).to_list(1)
    total_count = count_result[0]["total"] if count_result else 0
    
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
        "per_page": per_page,
        "query": q
    }

@router.get("/{blog_id}")
async def get_blog_by_id(
    blog_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """Get a specific blog by ID"""
    db = await get_database()
    
    if not ObjectId.is_valid(blog_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid blog ID"
        )
    
    # Get blog with author info
    pipeline = [
        {"$match": {"_id": ObjectId(blog_id)}},
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
    
    blogs = await db.blogs.aggregate(pipeline).to_list(1)
    
    if not blogs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog not found"
        )
    
    blog = blogs[0]
    blog["timestamp"] = format_timestamp(blog["timestamp"])
    blog["is_upvoted"] = (
        current_user and current_user["clerk_id"] in blog.get("upvoted_by", [])
    )
    
    return convert_objectid_to_str(blog)

@router.post("")
async def create_blog(
    blog_data: BlogCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new blog post"""
    db = await get_database()
    
    # Sanitize HTML content
    sanitized_content = sanitize_html(blog_data.content)
    
    blog_dict = blog_data.dict()
    blog_dict["content"] = sanitized_content
    blog_dict["author_id"] = current_user["clerk_id"]
    blog_dict["upvotes"] = 0
    blog_dict["upvoted_by"] = []
    blog_dict["created_at"] = datetime.utcnow()
    blog_dict["updated_at"] = datetime.utcnow()
    
    result = await db.blogs.insert_one(blog_dict)
    
    # Get the created blog with author info
    created_blog = await get_blog_by_id(str(result.inserted_id), current_user)
    
    return created_blog

@router.put("/{blog_id}")
async def update_blog(
    blog_id: str,
    blog_update: BlogUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update a blog post (only by the author)"""
    db = await get_database()
    
    if not ObjectId.is_valid(blog_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid blog ID"
        )
    
    # Check if blog exists and user is the author
    blog = await db.blogs.find_one({"_id": ObjectId(blog_id)})
    
    if not blog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog not found"
        )
    
    if blog["author_id"] != current_user["clerk_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own blogs"
        )
    
    # Update blog
    update_data = {k: v for k, v in blog_update.dict().items() if v is not None}
    
    if "content" in update_data:
        update_data["content"] = sanitize_html(update_data["content"])
    
    update_data["updated_at"] = datetime.utcnow()
    
    await db.blogs.update_one(
        {"_id": ObjectId(blog_id)},
        {"$set": update_data}
    )
    
    # Return updated blog
    return await get_blog_by_id(blog_id, current_user)

@router.delete("/{blog_id}")
async def delete_blog(
    blog_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete a blog post (only by the author)"""
    db = await get_database()
    
    if not ObjectId.is_valid(blog_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid blog ID"
        )
    
    # Check if blog exists and user is the author
    blog = await db.blogs.find_one({"_id": ObjectId(blog_id)})
    
    if not blog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog not found"
        )
    
    if blog["author_id"] != current_user["clerk_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own blogs"
        )
    
    await db.blogs.delete_one({"_id": ObjectId(blog_id)})
    
    return {"message": "Blog deleted successfully"}

@router.post("/{blog_id}/upvote")
async def toggle_blog_upvote(
    blog_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Toggle upvote on a blog post"""
    db = await get_database()
    
    if not ObjectId.is_valid(blog_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid blog ID"
        )
    
    blog = await db.blogs.find_one({"_id": ObjectId(blog_id)})
    
    if not blog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog not found"
        )
    
    user_id = current_user["clerk_id"]
    upvoted_by = blog.get("upvoted_by", [])
    
    if user_id in upvoted_by:
        # Remove upvote
        await db.blogs.update_one(
            {"_id": ObjectId(blog_id)},
            {
                "$pull": {"upvoted_by": user_id},
                "$inc": {"upvotes": -1}
            }
        )
        action = "removed"
    else:
        # Add upvote
        await db.blogs.update_one(
            {"_id": ObjectId(blog_id)},
            {
                "$addToSet": {"upvoted_by": user_id},
                "$inc": {"upvotes": 1}
            }
        )
        action = "added"
    
    # Get updated blog
    updated_blog = await db.blogs.find_one({"_id": ObjectId(blog_id)})
    
    return {
        "message": f"Upvote {action} successfully",
        "upvotes": updated_blog["upvotes"],
        "is_upvoted": user_id in updated_blog.get("upvoted_by", [])
    } 