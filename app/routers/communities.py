from fastapi import APIRouter, HTTPException, status, Query, Header, File, UploadFile
from fastapi.responses import StreamingResponse
from app.database import get_database
from app.models.community import (
    CommunityCreate, CommunityUpdate, CommunityResponse, CommunitySettings,
    CommunityPostCreate, CommunityPostUpdate, CommunityPostResponse,
    ImageUploadResponse, CommunityInvite, SSEEvent, SSEEventType
)
from app.models.presence import CommunityPresenceResponse, PresenceResponse, PresenceStatus
from app.utils.helpers import convert_objectid_to_str, format_timestamp, sanitize_html
from typing import Optional, List
from datetime import datetime, timedelta
from bson import ObjectId
import secrets
import os
import shutil
import json
import asyncio
from pathlib import Path
import firebase_admin
from firebase_admin import storage as fb_storage

router = APIRouter()

# IMAGE UPLOAD ENDPOINTS

@router.post("/upload/logo")
async def upload_community_logo(
    file: UploadFile = File(...),
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Upload community logo image to Firebase Storage"""
    allowed_types = ["image/jpeg", "image/png", "image/jpg", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG, PNG, JPG, and WebP images are allowed"
        )
    content = await file.read()
    file_size = len(content)
    if file_size > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must be less than 5MB"
        )
    # Upload to Firebase Storage
    bucket = fb_storage.bucket()
    file_extension = file.filename.split(".")[-1]
    unique_filename = f"community_logos/{secrets.token_hex(16)}.{file_extension}"
    blob = bucket.blob(unique_filename)
    blob.upload_from_string(content, content_type=file.content_type)
    blob.make_public()
    file_url = blob.public_url
    return ImageUploadResponse(
        url=file_url,
        filename=unique_filename,
        size=file_size
    )

@router.post("/upload/cover")
async def upload_community_cover(
    file: UploadFile = File(...),
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Upload community cover image to Firebase Storage"""
    allowed_types = ["image/jpeg", "image/png", "image/jpg", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG, PNG, JPG, and WebP images are allowed"
        )
    content = await file.read()
    file_size = len(content)
    if file_size > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must be less than 10MB"
        )
    # Upload to Firebase Storage
    bucket = fb_storage.bucket()
    file_extension = file.filename.split(".")[-1]
    unique_filename = f"community_covers/{secrets.token_hex(16)}.{file_extension}"
    blob = bucket.blob(unique_filename)
    blob.upload_from_string(content, content_type=file.content_type)
    blob.make_public()
    file_url = blob.public_url
    return ImageUploadResponse(
        url=file_url,
        filename=unique_filename,
        size=file_size
    )

# CATEGORY MANAGEMENT ENDPOINTS

@router.get("/categories")
async def get_available_categories():
    """Get list of available community categories from database"""
    db = await get_database()
    
    # Get all active categories from database
    categories_docs = await db.categories.find({"is_active": True}).sort("name", 1).to_list(None)
    
    # If no categories exist, seed the database with default categories
    if not categories_docs:
        await seed_default_categories(db)
        categories_docs = await db.categories.find({"is_active": True}).sort("name", 1).to_list(None)
    
    # Extract category names
    categories = [cat["name"] for cat in categories_docs]
    
    return {"categories": categories}

async def seed_default_categories(db):
    """Seed database with default categories"""
    default_categories = [
        "Technology",
        "Programming", 
        "Design",
        "Business",
        "Education",
        "Science",
        "Arts",
        "Gaming",
        "Health",
        "Sports",
        "Music",
        "Food",
        "Travel",
        "Books",
        "Movies",
        "Photography",
        "Finance",
        "Marketing",
        "Entrepreneurship",
        "Personal Development"
    ]
    
    # Insert categories one by one to avoid duplicates
    added_count = 0
    for category in default_categories:
        # Check if category already exists
        existing = await db.categories.find_one({
            "name": category,
            "is_active": True
        })
        
        if not existing:
            category_doc = {
                "name": category,
                "slug": category.lower().replace(" ", "-"),
                "description": f"Communities focused on {category.lower()}",
                "created_by": "system",
                "created_at": datetime.utcnow(),
                "is_active": True,
                "is_default": True,
                "community_count": 0
            }
            
            await db.categories.insert_one(category_doc)
            added_count += 1
    
    print(f"✅ Seeded {added_count} new default categories")

async def update_category_counts(db, categories: List[str], increment: bool = True):
    """Update community counts for categories"""
    if not categories:
        return
    
    change = 1 if increment else -1
    
    # Update counts for all categories
    await db.categories.update_many(
        {"name": {"$in": categories}, "is_active": True},
        {"$inc": {"community_count": change}}
    )

async def initialize_categories():
    """Initialize categories in database if they don't exist"""
    db = await get_database()
    
    # Check if categories collection exists and has data
    categories_count = await db.categories.count_documents({"is_active": True})
    
    if categories_count == 0:
        await seed_default_categories(db)
        print("✅ Categories initialized successfully")
    else:
        print(f"✅ Found {categories_count} existing categories")
    
    return True

@router.post("/categories")
async def add_custom_category(
    category_name: str,
    description: Optional[str] = None,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Add a custom category"""
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
    existing = await db.categories.find_one({
        "name": {"$regex": f"^{category_name}$", "$options": "i"},
        "is_active": True
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category already exists"
        )
    
    # Create category slug
    slug = category_name.lower().replace(" ", "-").replace("&", "and")
    
    # Add new category
    category_doc = {
        "name": category_name,
        "slug": slug,
        "description": description or f"Communities focused on {category_name.lower()}",
        "created_by": x_user_id,
        "created_at": datetime.utcnow(),
        "is_active": True,
        "is_default": False,
        "community_count": 0
    }
    
    result = await db.categories.insert_one(category_doc)
    
    return {
        "message": "Category added successfully",
        "category": {
            "id": str(result.inserted_id),
            "name": category_name,
            "slug": slug,
            "description": category_doc["description"]
                 }
     }

@router.get("/categories/detailed")
async def get_detailed_categories():
    """Get detailed category information with community counts"""
    db = await get_database()
    
    # Get all active categories first
    categories = await db.categories.find({"is_active": True}).sort("name", 1).to_list(None)
    
    # Calculate community counts for each category
    for category in categories:
        community_count = await db.communities.count_documents({
            "categories": category["name"]
        })
        category["community_count"] = community_count
    
    # If no categories exist, seed the database
    if not categories:
        await seed_default_categories(db)
        categories = await db.categories.find({"is_active": True}).sort("name", 1).to_list(None)
        # Calculate community counts for seeded categories
        for category in categories:
            community_count = await db.communities.count_documents({
                "categories": category["name"]
            })
            category["community_count"] = community_count
    
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
            "description": cat.get("description", f"Communities focused on {cat['name'].lower()}"),
            "community_count": cat.get("community_count", 0),
            "is_default": cat.get("is_default", False),
            "created_at": created_at_formatted
        })
    
    return {"categories": formatted_categories}

@router.get("/categories/{category_slug}")
async def get_category_by_slug(category_slug: str):
    """Get a specific category by slug"""
    db = await get_database()
    
    category = await db.categories.find_one({"slug": category_slug, "is_active": True})
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    # Get community count
    community_count = await db.communities.count_documents({"categories": category["name"]})
    
    return {
        "id": str(category["_id"]),
        "name": category["name"],
        "slug": category["slug"],
        "description": category["description"],
        "community_count": community_count,
        "is_default": category.get("is_default", False),
        "created_at": format_timestamp(category["created_at"])
    }

@router.put("/categories/{category_id}")
async def update_category(
    category_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Update a category (only by creator or admin)"""
    db = await get_database()
    
    if not ObjectId.is_valid(category_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid category ID"
        )
    
    # Check if category exists
    category = await db.categories.find_one({"_id": ObjectId(category_id)})
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    # Check permissions (creator or admin)
    if category["created_by"] != x_user_id and category.get("created_by") != "system":
        # For now, only allow creator to edit. Later you can add admin role checks
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit categories you created"
        )
    
    # Prepare update data
    update_data = {}
    if name:
        name = name.strip()
        if len(name) < 2 or len(name) > 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category name must be between 2 and 50 characters"
            )
        
        # Check if new name already exists
        existing = await db.categories.find_one({
            "_id": {"$ne": ObjectId(category_id)},
            "name": {"$regex": f"^{name}$", "$options": "i"},
            "is_active": True
        })
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category name already exists"
            )
        
        update_data["name"] = name
        update_data["slug"] = name.lower().replace(" ", "-").replace("&", "and")
    
    if description:
        update_data["description"] = description
    
    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        await db.categories.update_one(
            {"_id": ObjectId(category_id)},
            {"$set": update_data}
        )
    
    # Return updated category
    updated_category = await db.categories.find_one({"_id": ObjectId(category_id)})
    community_count = await db.communities.count_documents({"categories": updated_category["name"]})
    
    return {
        "id": str(updated_category["_id"]),
        "name": updated_category["name"],
        "slug": updated_category["slug"],
        "description": updated_category["description"],
        "community_count": community_count,
        "is_default": updated_category.get("is_default", False),
        "created_at": format_timestamp(updated_category["created_at"])
    }

@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: str,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Soft delete a category (only by creator or admin)"""
    db = await get_database()
    
    if not ObjectId.is_valid(category_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid category ID"
        )
    
    # Check if category exists
    category = await db.categories.find_one({"_id": ObjectId(category_id)})
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    # Check permissions
    if category["created_by"] != x_user_id and category.get("created_by") != "system":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete categories you created"
        )
    
    # Don't allow deleting if communities are using this category
    community_count = await db.communities.count_documents({"categories": category["name"]})
    if community_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete category. {community_count} communities are using this category."
        )
    
    # Soft delete by setting is_active to False
    await db.categories.update_one(
        {"_id": ObjectId(category_id)},
        {"$set": {"is_active": False, "deleted_at": datetime.utcnow()}}
    )
    
    return {"message": "Category deleted successfully"}

@router.post("/categories/recalculate-counts")
async def recalculate_category_counts(
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Recalculate community counts for all categories (admin function)"""
    db = await get_database()
    
    # For now, anyone can run this. Later you can add admin role checks
    # Verify user exists
    user = await db.users.find_one({"_id": x_user_id})
    if not user and ObjectId.is_valid(x_user_id):
        user = await db.users.find_one({"_id": ObjectId(x_user_id)})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get all active categories
    categories = await db.categories.find({"is_active": True}).to_list(None)
    
    updated_count = 0
    for category in categories:
        # Count communities using this category
        actual_count = await db.communities.count_documents({
            "categories": category["name"]
        })
        
        # Update if different
        if category.get("community_count", 0) != actual_count:
            await db.categories.update_one(
                {"_id": category["_id"]},
                {"$set": {"community_count": actual_count}}
            )
            updated_count += 1
    
    return {
        "message": f"Recalculated counts for {updated_count} categories",
        "total_categories": len(categories),
        "updated_categories": updated_count
    }

@router.post("/categories/seed")
async def manual_seed_categories(
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Manually seed categories (for testing/debugging)"""
    db = await get_database()
    
    # Verify user exists
    user = await db.users.find_one({"_id": x_user_id})
    if not user and ObjectId.is_valid(x_user_id):
        user = await db.users.find_one({"_id": ObjectId(x_user_id)})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check existing categories
    existing_count = await db.categories.count_documents({"is_active": True})
    
    # Force seed default categories
    await seed_default_categories(db)
    
    # Check new count
    new_count = await db.categories.count_documents({"is_active": True})
    
    return {
        "message": "Categories seeded successfully",
        "existing_categories": existing_count,
        "new_total": new_count,
        "added": new_count - existing_count
    }

# ENHANCED COMMUNITY ENDPOINTS

@router.get("")
async def get_communities(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    access_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    order_by: Optional[str] = Query("newest", description="Sort order: newest, oldest, most_members, least_members, alphabetical, alphabetical_desc")
):
    """Get all communities with pagination, filtering, and sorting"""
    db = await get_database()
    
    # Build filter
    filter_query = {}
    if access_type:
        filter_query["access_type"] = access_type
    if category:
        filter_query["categories"] = {"$in": [category]}
    
    # Build sort criteria
    sort_mapping = {
        "newest": ("created_at", -1),
        "oldest": ("created_at", 1),
        "most_members": ("member_count", -1),
        "least_members": ("member_count", 1),
        "alphabetical": ("name", 1),
        "alphabetical_desc": ("name", -1)
    }
    
    # Default to newest if invalid order_by provided
    if order_by not in sort_mapping:
        order_by = "newest"
    
    sort_field, sort_direction = sort_mapping[order_by]
    
    skip = (page - 1) * per_page
    
    communities = await db.communities.find(filter_query)\
        .sort(sort_field, sort_direction)\
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
        "per_page": per_page,
        "order_by": order_by
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
    """Create a new community with enhanced features"""
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
    
    # Validate custom domain if provided
    if community_data.custom_domain:
        existing_domain = await db.communities.find_one({"custom_domain": community_data.custom_domain})
        if existing_domain:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Custom domain already exists"
            )
    
    community_dict = community_data.dict()
    community_dict["creator_id"] = x_user_id
    community_dict["member_count"] = 1
    community_dict["members"] = [x_user_id]
    community_dict["created_at"] = datetime.utcnow()
    community_dict["updated_at"] = datetime.utcnow()
    
    # Generate invite code for invite-only communities
    if community_data.access_type == "invite":
        community_dict["invite_code"] = secrets.token_urlsafe(8)
    
    result = await db.communities.insert_one(community_dict)
    
    # Create default channels for the new community
    from app.routers.channels import create_default_channels
    await create_default_channels(db, str(result.inserted_id), x_user_id)
    
    # Update category counts
    if community_data.categories:
        await update_category_counts(db, community_data.categories, increment=True)
    
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
    
    # Validate Clerk user ID from header
    if not x_user_id or len(x_user_id.strip()) == 0:
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
    
    # Validate Clerk user ID from header
    if not x_user_id or len(x_user_id.strip()) == 0:
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
    
    # Update category counts before deletion
    if community.get("categories"):
        await update_category_counts(db, community["categories"], increment=False)
    
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
    
    # Validate Clerk user ID from header
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
    
    # Validate Clerk user ID from header
    if not x_user_id or len(x_user_id.strip()) == 0:
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
    
    # Get posts directly and add author info separately
    posts = await db.posts.find(filter_query)\
        .sort("created_at", -1)\
        .skip(skip)\
        .limit(per_page)\
        .to_list(per_page)
    
    total_count = await db.posts.count_documents(filter_query)
    
    # Get author information for each post
    formatted_posts = []
    for post in posts:
        # Get author info
        author = await db.users.find_one({"_id": post["author_id"]})
        if author:
            author_info = {
                "id": str(author["_id"]),
                "name": author["name"],
                "username": author.get("username", ""),
                "avatar": author.get("avatar", "")
            }
        else:
            author_info = {
                "id": post["author_id"],
                "name": "Unknown User",
                "username": "unknown",
                "avatar": ""
            }
        
        formatted_post = {
            "id": str(post["_id"]),
            "content": post["content"],
            "author": author_info,
            "type": post.get("type", "message"),
            "community_id": post["community_id"],
            "channel_id": post.get("channel_id"),
            "reply_to": post.get("reply_to"),
            "created_at": format_timestamp(post["created_at"]),
            "updated_at": format_timestamp(post.get("updated_at", post["created_at"])),
            "is_edited": post.get("is_edited", False),
            "edited_at": format_timestamp(post["edited_at"]) if post.get("edited_at") else None,
            "upvotes": post.get("upvotes", 0),
            "comments": post.get("comments", 0)
        }
        formatted_posts.append(formatted_post)
    
    return {
        "posts": formatted_posts,
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
    
    # Validate Clerk user ID from header
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
    
    result = await db.posts.insert_one(post_dict)
    
    # Get the created post with author info
    created_post = await db.posts.find_one({"_id": result.inserted_id})
    
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
    post = await db.posts.find_one({
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
    
    await db.posts.update_one(
        {"_id": ObjectId(post_id)},
        {"$set": update_data}
    )
    
    # Return updated post
    updated_post = await db.posts.find_one({"_id": ObjectId(post_id)})
    
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
    post = await db.posts.find_one({
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
    
    await db.posts.delete_one({"_id": ObjectId(post_id)})
    
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
    post = await db.posts.find_one({
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
        await db.posts.update_one(
            {"_id": ObjectId(post_id)},
            {
                "$pull": {"upvoted_by": x_user_id},
                "$inc": {"upvotes": -1}
            }
        )
        action = "removed"
    else:
        # Add upvote
        await db.posts.update_one(
            {"_id": ObjectId(post_id)},
            {
                "$addToSet": {"upvoted_by": x_user_id},
                "$inc": {"upvotes": 1}
            }
        )
        action = "added"
    
    # Get updated post
    updated_post = await db.posts.find_one({"_id": ObjectId(post_id)})
    
    return {
        "message": f"Upvote {action} successfully",
        "upvotes": updated_post["upvotes"],
        "is_upvoted": not is_upvoted
    }

# INVITE MANAGEMENT ENDPOINTS

@router.post("/{community_id}/invites")
async def generate_invite_code(
    community_id: str,
    expires_in_hours: Optional[int] = Query(None, description="Hours until invite expires"),
    max_uses: Optional[int] = Query(None, description="Maximum number of uses"),
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Generate invite code for invite-only community (admin only)"""
    db = await get_database()
    
    if not ObjectId.is_valid(community_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community ID"
        )
    
    # Validate Clerk user ID from header
    if not x_user_id or len(x_user_id.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID from header"
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
            detail="Only community admin can generate invite codes"
        )
    
    # Generate invite
    invite_code = secrets.token_urlsafe(12)
    expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours) if expires_in_hours else None
    
    invite_doc = {
        "community_id": community_id,
        "invite_code": invite_code,
        "created_by": x_user_id,
        "expires_at": expires_at,
        "max_uses": max_uses,
        "current_uses": 0,
        "created_at": datetime.utcnow(),
        "is_active": True
    }
    
    await db.community_invites.insert_one(invite_doc)
    
    return {
        "invite_code": invite_code,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "max_uses": max_uses,
        "community_name": community["name"]
    }

@router.post("/join-by-invite")
async def join_community_by_invite(
    invite_code: str,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Join a community using invite code"""
    db = await get_database()
    
    # Validate user ID
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
    
    # Find and validate invite
    invite = await db.community_invites.find_one({"invite_code": invite_code, "is_active": True})
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired invite code"
        )
    
    # Check if invite has expired
    if invite.get("expires_at") and invite["expires_at"] < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invite code has expired"
        )
    
    # Check if invite has reached max uses
    if invite.get("max_uses") and invite["current_uses"] >= invite["max_uses"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invite code has reached maximum uses"
        )
    
    # Get community
    community = await db.communities.find_one({"_id": ObjectId(invite["community_id"])})
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
        {"_id": ObjectId(invite["community_id"])},
        {
            "$addToSet": {"members": x_user_id},
            "$inc": {"member_count": 1}
        }
    )
    
    # Increment invite usage
    await db.community_invites.update_one(
        {"_id": invite["_id"]},
        {"$inc": {"current_uses": 1}}
    )
    
    return {
        "message": f"Successfully joined {community['name']}",
        "community": {
            "id": str(community["_id"]),
            "name": community["name"],
            "description": community["description"]
        }
    }

@router.get("/{community_id}/invites")
async def list_community_invites(
    community_id: str,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """List all active invites for a community (admin only)"""
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
    
    if community["creator_id"] != x_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only community admin can view invites"
        )
    
    # Get all active invites
    invites = await db.community_invites.find({
        "community_id": community_id,
        "is_active": True
    }).to_list(None)
    
    # Format response
    formatted_invites = []
    for invite in invites:
        formatted_invites.append({
            "invite_code": invite["invite_code"],
            "created_at": format_timestamp(invite["created_at"]),
            "expires_at": format_timestamp(invite["expires_at"]) if invite.get("expires_at") else None,
            "max_uses": invite.get("max_uses"),
            "current_uses": invite["current_uses"],
            "created_by": invite["created_by"]
        })
    
    return {"invites": formatted_invites}

@router.delete("/{community_id}/invites/{invite_code}")
async def deactivate_invite(
    community_id: str,
    invite_code: str,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Deactivate an invite code (admin only)"""
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
    
    if community["creator_id"] != x_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only community admin can deactivate invites"
        )
    
    # Deactivate invite
    result = await db.community_invites.update_one(
        {"community_id": community_id, "invite_code": invite_code},
        {"$set": {"is_active": False}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite code not found"
        )
    
    return {"message": "Invite code deactivated successfully"}

# REAL-TIME COMMUNICATION ENDPOINTS

@router.get("/{community_id}/posts/stream")
async def stream_community_updates(
    community_id: str,
    channel_id: Optional[str] = Query(None, description="Filter by specific channel"),
    after: Optional[str] = Query(None, description="Get events after this message ID"),
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Server-Sent Events stream for real-time community updates"""
    
    if not ObjectId.is_valid(community_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid community ID"
        )
    
    # Validate user access
    db = await get_database()
    community = await db.communities.find_one({"_id": ObjectId(community_id)})
    if not community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found"
        )
    
    if x_user_id not in community.get("members", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be a member to receive updates"
        )
    
    async def event_generator():
        """Generate SSE events"""
        last_check = datetime.utcnow()
        current_community = community  # Initialize community reference for the generator
        
        # Send initial connection event
        connection_event = SSEEvent(
            type=SSEEventType.MESSAGE,
            data={"status": "connected", "message": "Connected to community stream"},
            community_id=community_id,
            channel_id=channel_id,
            timestamp=format_timestamp(datetime.utcnow())
        )
        yield f"data: {json.dumps(connection_event.dict())}\n\n"
        
        while True:
            try:
                # Check for new messages
                filter_query = {
                    "community_id": community_id,
                    "created_at": {"$gt": last_check}
                }
                
                if channel_id:
                    filter_query["channel_id"] = channel_id
                
                if after and ObjectId.is_valid(after):
                    filter_query["_id"] = {"$gt": ObjectId(after)}
                
                # Get new messages
                new_messages = await db.posts.find(filter_query)\
                    .sort("created_at", 1)\
                    .to_list(50)  # Limit to 50 messages per check
                
                for message in new_messages:
                    # Get author info
                    author = await db.users.find_one({"_id": message["author_id"]})
                    if author:
                        author_info = {
                            "id": str(author["_id"]),
                            "name": author["name"],
                            "username": author.get("username", ""),
                            "avatar": author.get("avatar", "")
                        }
                    else:
                        author_info = {
                            "id": message["author_id"],
                            "name": "Unknown User",
                            "username": "unknown",
                            "avatar": ""
                        }
                    
                    # Create message event
                    message_data = {
                        "id": str(message["_id"]),
                        "content": message["content"],
                        "author": author_info,
                        "type": message["type"],
                        "channel_id": message.get("channel_id"),
                        "community_id": community_id,
                        "reply_to": message.get("reply_to"),
                        "created_at": format_timestamp(message["created_at"]),
                        "updated_at": format_timestamp(message.get("updated_at", message["created_at"])),
                        "is_edited": message.get("is_edited", False),
                        "edited_at": format_timestamp(message["edited_at"]) if message.get("edited_at") else None
                    }
                    
                    message_event = SSEEvent(
                        type=SSEEventType.MESSAGE,
                        data=message_data,
                        community_id=community_id,
                        channel_id=message.get("channel_id"),
                        timestamp=format_timestamp(message["created_at"])
                    )
                    
                    yield f"data: {json.dumps(message_event.dict())}\n\n"
                
                # Check for presence updates
                presence_updates = await db.user_presence.find({
                    "user_id": {"$in": current_community.get("members", [])},
                    "updated_at": {"$gt": last_check}
                }).to_list(None)
                
                for presence in presence_updates:
                    presence_data = {
                        "user_id": presence["user_id"],
                        "status": presence["status"],
                        "custom_message": presence.get("custom_message"),
                        "last_seen": format_timestamp(presence["last_seen"]),
                        "updated_at": format_timestamp(presence["updated_at"])
                    }
                    
                    presence_event = SSEEvent(
                        type=SSEEventType.PRESENCE,
                        data=presence_data,
                        community_id=community_id,
                        channel_id=None,
                        timestamp=format_timestamp(presence["updated_at"])
                    )
                    
                    yield f"data: {json.dumps(presence_event.dict())}\n\n"
                
                # Check for new members
                updated_community = await db.communities.find_one({"_id": ObjectId(community_id)})
                current_members = set(updated_community.get("members", []))
                previous_members = set(current_community.get("members", []))
                
                new_members = current_members - previous_members
                left_members = previous_members - current_members
                
                for new_member_id in new_members:
                    user = await db.users.find_one({"_id": new_member_id})
                    if user:
                        join_data = {
                            "user_id": new_member_id,
                            "name": user["name"],
                            "username": user.get("username", ""),
                            "avatar": user.get("avatar", "")
                        }
                        
                        join_event = SSEEvent(
                            type=SSEEventType.USER_JOIN,
                            data=join_data,
                            community_id=community_id,
                            channel_id=None,
                            timestamp=format_timestamp(datetime.utcnow())
                        )
                        
                        yield f"data: {json.dumps(join_event.dict())}\n\n"
                
                for left_member_id in left_members:
                    leave_data = {
                        "user_id": left_member_id
                    }
                    
                    leave_event = SSEEvent(
                        type=SSEEventType.USER_LEAVE,
                        data=leave_data,
                        community_id=community_id,
                        channel_id=None,
                        timestamp=format_timestamp(datetime.utcnow())
                    )
                    
                    yield f"data: {json.dumps(leave_event.dict())}\n\n"
                
                # Update community reference and last check time
                current_community = updated_community
                last_check = datetime.utcnow()
                
                # Send heartbeat every 30 seconds
                heartbeat_event = SSEEvent(
                    type="heartbeat",
                    data={"timestamp": format_timestamp(datetime.utcnow())},
                    community_id=community_id,
                    channel_id=None,
                    timestamp=format_timestamp(datetime.utcnow())
                )
                yield f"data: {json.dumps(heartbeat_event.dict())}\n\n"
                
                # Wait before next check
                await asyncio.sleep(2)  # Check every 2 seconds
                
            except Exception as e:
                # Send error event and break
                error_event = SSEEvent(
                    type="error",
                    data={"error": str(e), "message": "Stream error occurred"},
                    community_id=community_id,
                    channel_id=None,
                    timestamp=format_timestamp(datetime.utcnow())
                )
                yield f"data: {json.dumps(error_event.dict())}\n\n"
                break
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*"
        }
    )

# PRESENCE ENDPOINTS

@router.get("/{community_id}/presence")
async def get_community_presence(
    community_id: str,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Get presence status for all community members"""
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
            detail="You must be a member to view community presence"
        )
    
    # Get all member user IDs
    member_ids = community.get("members", [])
    
    # Get presence data for all members
    presences = await db.user_presence.find({"user_id": {"$in": member_ids}}).to_list(None)
    
    # Create presence map
    presence_map = {}
    online_count = 0
    
    for presence in presences:
        user_id = presence["user_id"]
        status = presence["status"]
        
        if status == PresenceStatus.ONLINE:
            online_count += 1
        
        presence_map[user_id] = PresenceResponse(
            user_id=user_id,
            status=status,
            custom_message=presence.get("custom_message"),
            last_seen=format_timestamp(presence["last_seen"]),
            updated_at=format_timestamp(presence["updated_at"])
        )
    
    # For members without presence records, set them as offline
    for member_id in member_ids:
        if member_id not in presence_map:
            presence_map[member_id] = PresenceResponse(
                user_id=member_id,
                status=PresenceStatus.OFFLINE,
                custom_message=None,
                last_seen=format_timestamp(datetime.utcnow()),
                updated_at=format_timestamp(datetime.utcnow())
            )
    
    return CommunityPresenceResponse(
        community_id=community_id,
        presences=presence_map,
        online_count=online_count,
        total_count=len(member_ids)
    ) 