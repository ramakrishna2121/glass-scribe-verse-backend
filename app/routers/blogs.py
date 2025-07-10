from fastapi import APIRouter, HTTPException, status, Query, Header
from app.database import get_database
from app.models.blog import BlogCreate, BlogUpdate, BlogResponse
from app.utils.helpers import convert_objectid_to_str, format_timestamp, sanitize_html
from typing import Optional, List
from datetime import datetime
from bson import ObjectId

router = APIRouter()

@router.get("")
async def get_blogs(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    category: Optional[str] = Query(None),
    author: Optional[str] = Query(None)
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
    
    # Get blogs first
    blogs = await db.blogs.find(filter_query)\
        .sort("created_at", -1)\
        .skip(skip)\
        .limit(per_page)\
        .to_list(per_page)
    
    total_count = await db.blogs.count_documents(filter_query)
    
    # Get unique author IDs
    author_ids = list(set(blog["author_id"] for blog in blogs))
    
    # Get all authors info - handle both string IDs (Clerk) and ObjectIds
    authors = {}
    for author_id in author_ids:
        # Try string ID first (Clerk ID), then ObjectId if needed
        author = await db.users.find_one({"_id": author_id})
        if not author and ObjectId.is_valid(author_id):
            author = await db.users.find_one({"_id": ObjectId(author_id)})
        
        if author:
            authors[author_id] = {
                "id": str(author["_id"]),
                "name": author["name"],
                "username": author.get("username", ""),
                "avatar": author.get("avatar", ""),
                "bio": author.get("bio", "")
            }
        else:
            authors[author_id] = {
                "id": author_id,
                "name": "Unknown User",
                "username": "",
                "avatar": "",
                "bio": ""
            }
    
    # Add author info to each blog
    for blog in blogs:
        blog["author"] = authors.get(blog["author_id"], {
            "id": blog["author_id"],
            "name": "Unknown User",
            "username": "",
            "avatar": "",
            "bio": ""
        })
        blog["timestamp"] = format_timestamp(blog["created_at"])
    
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
    per_page: int = Query(10, ge=1, le=50)
):
    """Search blogs by title, content, category, or author"""
    db = await get_database()
    
    skip = (page - 1) * per_page
    
    # Build search filter
    search_filter = {
        "$or": [
            {"title": {"$regex": q, "$options": "i"}},
            {"content": {"$regex": q, "$options": "i"}},
            {"category": {"$regex": q, "$options": "i"}},
            {"excerpt": {"$regex": q, "$options": "i"}}
        ]
    }
    
    # Get blogs first
    blogs = await db.blogs.find(search_filter)\
        .sort("created_at", -1)\
        .skip(skip)\
        .limit(per_page)\
        .to_list(per_page)
    
    total_count = await db.blogs.count_documents(search_filter)
    
    # Get unique author IDs
    author_ids = list(set(blog["author_id"] for blog in blogs))
    
    # Get all authors info - handle both string IDs (Clerk) and ObjectIds
    authors = {}
    for author_id in author_ids:
        # Try string ID first (Clerk ID), then ObjectId if needed
        author = await db.users.find_one({"_id": author_id})
        if not author and ObjectId.is_valid(author_id):
            author = await db.users.find_one({"_id": ObjectId(author_id)})
        
        if author:
            authors[author_id] = {
                "id": str(author["_id"]),
                "name": author["name"],
                "username": author.get("username", ""),
                "avatar": author.get("avatar", ""),
                "bio": author.get("bio", "")
            }
        else:
            authors[author_id] = {
                "id": author_id,
                "name": "Unknown User",
                "username": "",
                "avatar": "",
                "bio": ""
            }
    
    # Add author info to each blog
    for blog in blogs:
        blog["author"] = authors.get(blog["author_id"], {
            "id": blog["author_id"],
            "name": "Unknown User",
            "username": "",
            "avatar": "",
            "bio": ""
        })
        blog["timestamp"] = format_timestamp(blog["created_at"])
    
    return {
        "blogs": convert_objectid_to_str(blogs),
        "total": total_count,
        "page": page,
        "per_page": per_page,
        "query": q
    }

@router.get("/{blog_id}")
async def get_blog_by_id(blog_id: str):
    """Get a specific blog by ID"""
    db = await get_database()
    
    if not ObjectId.is_valid(blog_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid blog ID"
        )
    
    # Get blog first
    blog = await db.blogs.find_one({"_id": ObjectId(blog_id)})
    
    if not blog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog not found"
        )
    
    # Get author info separately - try string ID first (Clerk ID), then ObjectId if needed
    author_id = blog["author_id"]
    author = await db.users.find_one({"_id": author_id})
    if not author and ObjectId.is_valid(author_id):
        author = await db.users.find_one({"_id": ObjectId(author_id)})
    
    # Add author info to blog
    if author:
        blog["author"] = {
            "id": str(author["_id"]),
            "name": author["name"],
            "username": author.get("username", ""),
            "avatar": author.get("avatar", ""),
            "bio": author.get("bio", "")
        }
    else:
        # Author not found, set default
        blog["author"] = {
            "id": author_id,
            "name": "Unknown User",
            "username": "",
            "avatar": "",
            "bio": ""
        }
    
    blog["timestamp"] = format_timestamp(blog["created_at"])
    
    return convert_objectid_to_str(blog)

@router.post("")
async def create_blog(
    blog_data: BlogCreate,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Create a new blog (requires user ID from frontend Clerk authentication)"""
    db = await get_database()
    
    # Validate Clerk user ID format (should be a valid string identifier)
    if not x_user_id or len(x_user_id.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID from header"
        )
    
    # Verify author exists - try string ID first (Clerk ID), then ObjectId if needed
    author = await db.users.find_one({"_id": x_user_id})
    if not author and ObjectId.is_valid(x_user_id):
        author = await db.users.find_one({"_id": ObjectId(x_user_id)})
    
    if not author:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Please create user profile first."
        )
    
    # Sanitize HTML content
    sanitized_content = sanitize_html(blog_data.content)
    
    blog_dict = blog_data.dict()
    blog_dict["content"] = sanitized_content
    blog_dict["author_id"] = x_user_id
    blog_dict["upvotes"] = 0
    blog_dict["upvoted_by"] = []
    blog_dict["created_at"] = datetime.utcnow()
    blog_dict["updated_at"] = datetime.utcnow()
    
    result = await db.blogs.insert_one(blog_dict)
    
    # Return the created blog with author info
    return await get_blog_by_id(str(result.inserted_id))

@router.put("/{blog_id}")
async def update_blog(
    blog_id: str,
    blog_update: BlogUpdate,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Update a blog (only by the author)"""
    db = await get_database()
    
    if not ObjectId.is_valid(blog_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid blog ID"
        )
    
    # Validate Clerk user ID format
    if not x_user_id or len(x_user_id.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID from header"
        )
    
    # Check if blog exists and user is the author
    blog = await db.blogs.find_one({"_id": ObjectId(blog_id)})
    
    if not blog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog not found"
        )
    
    if blog["author_id"] != x_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own blogs"
        )
    
    # Sanitize HTML content if provided
    update_data = {k: v for k, v in blog_update.dict().items() if v is not None}
    if "content" in update_data:
        update_data["content"] = sanitize_html(update_data["content"])
    
    update_data["updated_at"] = datetime.utcnow()
    
    await db.blogs.update_one(
        {"_id": ObjectId(blog_id)},
        {"$set": update_data}
    )
    
    # Return updated blog
    return await get_blog_by_id(blog_id)

@router.delete("/{blog_id}")
async def delete_blog(
    blog_id: str,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Delete a blog (only by the author)"""
    db = await get_database()
    
    if not ObjectId.is_valid(blog_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid blog ID"
        )
    
    # Validate Clerk user ID format
    if not x_user_id or len(x_user_id.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID from header"
        )
    
    # Check if blog exists and user is the author
    blog = await db.blogs.find_one({"_id": ObjectId(blog_id)})
    
    if not blog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog not found"
        )
    
    if blog["author_id"] != x_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own blogs"
        )
    
    await db.blogs.delete_one({"_id": ObjectId(blog_id)})
    
    return {"message": "Blog deleted successfully"}

@router.post("/{blog_id}/upvote")
async def toggle_blog_upvote(
    blog_id: str,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Toggle upvote on a blog"""
    db = await get_database()
    
    if not ObjectId.is_valid(blog_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid blog ID"
        )
    
    # Validate Clerk user ID format
    if not x_user_id or len(x_user_id.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID from header"
        )
    
    # Verify user exists - try string ID first (Clerk ID), then ObjectId if needed
    user = await db.users.find_one({"_id": x_user_id})
    if not user and ObjectId.is_valid(x_user_id):
        user = await db.users.find_one({"_id": ObjectId(x_user_id)})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if blog exists
    blog = await db.blogs.find_one({"_id": ObjectId(blog_id)})
    if not blog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog not found"
        )
    
    # Toggle upvote
    is_upvoted = x_user_id in blog.get("upvoted_by", [])
    
    if is_upvoted:
        # Remove upvote
        await db.blogs.update_one(
            {"_id": ObjectId(blog_id)},
            {
                "$pull": {"upvoted_by": x_user_id},
                "$inc": {"upvotes": -1}
            }
        )
        action = "removed"
    else:
        # Add upvote
        await db.blogs.update_one(
            {"_id": ObjectId(blog_id)},
            {
                "$addToSet": {"upvoted_by": x_user_id},
                "$inc": {"upvotes": 1}
            }
        )
        action = "added"
    
    # Get updated blog
    updated_blog = await db.blogs.find_one({"_id": ObjectId(blog_id)})
    
    return {
        "message": f"Upvote {action} successfully",
        "upvotes": updated_blog["upvotes"],
        "is_upvoted": not is_upvoted
    } 