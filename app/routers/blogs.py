from fastapi import APIRouter, HTTPException, status, Query, Header, File, UploadFile
from app.database import get_database
from app.models.blog import BlogCreate, BlogUpdate, BlogResponse
from app.utils.helpers import convert_objectid_to_str, format_timestamp, sanitize_html
from typing import Optional, List
from datetime import datetime
from bson import ObjectId
import secrets
from firebase_admin import storage as fb_storage

router = APIRouter()

# BLOG IMAGE UPLOAD ENDPOINT

@router.post("/upload/image")
async def upload_blog_image(
    file: UploadFile = File(...),
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Upload blog featured image to Firebase Storage"""
    allowed_types = ["image/jpeg", "image/png", "image/jpg", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG, PNG, JPG, and WebP images are allowed"
        )
    
    content = await file.read()
    file_size = len(content)
    if file_size > 10 * 1024 * 1024:  # 10MB limit for blog images
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must be less than 10MB"
        )
    
    # Verify user exists
    db = await get_database()
    user = await db.users.find_one({"_id": x_user_id})
    if not user and ObjectId.is_valid(x_user_id):
        user = await db.users.find_one({"_id": ObjectId(x_user_id)})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Upload to Firebase Storage
    bucket = fb_storage.bucket()
    file_extension = file.filename.split(".")[-1]
    unique_filename = f"blog_images/{secrets.token_hex(16)}.{file_extension}"
    blob = bucket.blob(unique_filename)
    blob.upload_from_string(content, content_type=file.content_type)
    blob.make_public()
    file_url = blob.public_url
    
    return {
        "url": file_url,
        "filename": unique_filename,
        "size": file_size
    }

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

# BLOG CATEGORY MANAGEMENT ENDPOINTS

@router.get("/categories")
async def get_blog_categories():
    """Get list of available blog categories"""
    db = await get_database()
    
    # Get all active blog categories from database
    blog_categories = await db.blog_categories.find({"is_active": True}).sort("name", 1).to_list(None)
    
    # If no categories exist, seed with default blog categories
    if not blog_categories:
        await seed_default_blog_categories(db)
        blog_categories = await db.blog_categories.find({"is_active": True}).sort("name", 1).to_list(None)
    
    # Extract category names
    categories = [cat["name"] for cat in blog_categories]
    
    return {"categories": categories}

@router.get("/categories/detailed")
async def get_detailed_blog_categories():
    """Get detailed blog category information with blog counts"""
    db = await get_database()
    
    # Get all active blog categories first
    categories = await db.blog_categories.find({"is_active": True}).sort("name", 1).to_list(None)
    
    # Calculate blog counts for each category
    for category in categories:
        blog_count = await db.blogs.count_documents({
            "category": category["name"]
        })
        category["blog_count"] = blog_count
    
    # If no categories exist, seed the database
    if not categories:
        await seed_default_blog_categories(db)
        categories = await db.blog_categories.find({"is_active": True}).sort("name", 1).to_list(None)
        # Calculate blog counts for seeded categories
        for category in categories:
            blog_count = await db.blogs.count_documents({
                "category": category["name"]
            })
            category["blog_count"] = blog_count
    
    # Format response
    formatted_categories = []
    for cat in categories:
        try:
            created_at_formatted = format_timestamp(cat["created_at"]) if cat.get("created_at") else "Unknown"
        except:
            created_at_formatted = "Unknown"
            
        formatted_categories.append({
            "id": str(cat["_id"]),
            "name": cat["name"],
            "slug": cat.get("slug", cat["name"].lower().replace(" ", "-")),
            "description": cat.get("description", f"Blogs focused on {cat['name'].lower()}"),
            "blog_count": cat.get("blog_count", 0),
            "is_default": cat.get("is_default", False),
            "created_at": created_at_formatted
        })
    
    return {"categories": formatted_categories}

@router.post("/categories")
async def add_custom_blog_category(
    category_name: str,
    description: Optional[str] = None,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Add a custom blog category"""
    db = await get_database()
    
    # Validate user exists
    user = await db.users.find_one({"_id": x_user_id})
    if not user and ObjectId.is_valid(x_user_id):
        user = await db.users.find_one({"_id": ObjectId(x_user_id)})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Validate category name
    category_name = category_name.strip()
    if len(category_name) < 2 or len(category_name) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category name must be between 2 and 50 characters"
        )
    
    # Check if category already exists (case-insensitive)
    existing = await db.blog_categories.find_one({
        "name": {"$regex": f"^{category_name}$", "$options": "i"},
        "is_active": True
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Blog category already exists"
        )
    
    # Create category slug
    slug = category_name.lower().replace(" ", "-").replace("&", "and")
    
    # Add new blog category
    category_doc = {
        "name": category_name,
        "slug": slug,
        "description": description or f"Blogs focused on {category_name.lower()}",
        "created_by": x_user_id,
        "created_at": datetime.utcnow(),
        "is_active": True,
        "is_default": False,
        "blog_count": 0
    }
    
    result = await db.blog_categories.insert_one(category_doc)
    
    return {
        "message": "Blog category added successfully",
        "category": {
            "id": str(result.inserted_id),
            "name": category_name,
            "slug": slug,
            "description": category_doc["description"]
        }
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



async def seed_default_blog_categories(db):
    """Seed database with default blog categories"""
    default_blog_categories = [
        "Technology", "Design", "Programming", "Web Development", "Mobile Development",
        "Data Science", "AI & Machine Learning", "DevOps", "Cybersecurity", "UI/UX",
        "Frontend", "Backend", "Full Stack", "JavaScript", "Python", "React", "Node.js",
        "Tutorials", "Tips & Tricks", "Best Practices", "Career", "Freelancing",
        "Startup", "Business", "Marketing", "Productivity", "Tools & Resources"
    ]
    
    added_count = 0
    
    # Insert categories one by one to avoid duplicates
    for category in default_blog_categories:
        # Check if category already exists
        existing = await db.blog_categories.find_one({
            "name": category,
            "is_active": True
        })
        
        if not existing:
            category_doc = {
                "name": category,
                "slug": category.lower().replace(" ", "-").replace("&", "and"),
                "description": f"Blogs focused on {category.lower()}",
                "created_by": "system",
                "created_at": datetime.utcnow(),
                "is_active": True,
                "is_default": True,
                "blog_count": 0
            }
            
            await db.blog_categories.insert_one(category_doc)
            added_count += 1
    
    if added_count > 0:
        print(f"✅ Seeded {added_count} new default blog categories") 