from fastapi import APIRouter, HTTPException, status, Query, Header
from app.database import get_database
from app.models.user import UserCreate, UserUpdate, User
from app.utils.helpers import convert_objectid_to_str, format_timestamp
from typing import Optional, List
from datetime import datetime
from bson import ObjectId

router = APIRouter()

@router.get("")
async def get_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    search: Optional[str] = Query(None)
):
    """Get all users with pagination and optional search"""
    db = await get_database()
    
    # Build filter
    filter_query = {}
    if search:
        filter_query = {
            "$or": [
                {"name": {"$regex": search, "$options": "i"}},
                {"username": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}}
            ]
        }
    
    skip = (page - 1) * per_page
    
    users = await db.users.find(filter_query)\
        .sort("created_at", -1)\
        .skip(skip)\
        .limit(per_page)\
        .to_list(per_page)
    
    total_count = await db.users.count_documents(filter_query)
    
    # Format timestamps and exclude sensitive fields
    for user in users:
        user["created_at"] = format_timestamp(user["created_at"])
        # Remove sensitive fields from public listing
        user.pop("email", None)
    
    return {
        "users": convert_objectid_to_str(users),
        "total": total_count,
        "page": page,
        "per_page": per_page
          }


@router.get("/me/profile")
async def get_my_profile(
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Get current user's profile data using authentication header (same as /profile)"""
    # Validate Clerk user ID from header
    if not x_user_id or len(x_user_id.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID from header"
        )
    
    db = await get_database()
    return await _get_profile_data(x_user_id, db)

@router.get("/profile")
async def get_user_profile(
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Get user profile data using authentication header"""
    # Validate Clerk user ID from header
    if not x_user_id or len(x_user_id.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID from header"
        )
    
    db = await get_database()
    return await _get_profile_data(x_user_id, db)

@router.get("/{user_id}")
async def get_user_by_id(user_id: str):
    """Get a specific user by ID"""
    db = await get_database()
    
    # Try to find user by string ID first (Clerk ID), then by ObjectId if needed
    user = await db.users.find_one({"_id": user_id})
    
    # If not found and user_id looks like ObjectId, try as ObjectId
    if not user and ObjectId.is_valid(user_id):
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user["created_at"] = format_timestamp(user["created_at"])
    
    return convert_objectid_to_str(user)

@router.post("")
async def create_user(
    user_data: UserCreate,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Create a new user with Clerk user ID"""
    db = await get_database()
    
    # Validate Clerk user ID format (should be a valid string identifier)
    if not x_user_id or len(x_user_id.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID from Clerk"
        )
    
    # Check if user with this Clerk ID already exists
    existing_user = await db.users.find_one({"_id": x_user_id})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists"
        )
    
    # Check if user with email already exists
    existing_email = await db.users.find_one({"email": user_data.email})
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Check if username already exists
    if user_data.username:
        existing_username = await db.users.find_one({"username": user_data.username})
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )
    
    user_dict = user_data.dict()
    user_dict["_id"] = x_user_id  # Use Clerk user ID as document ID
    user_dict["created_at"] = datetime.utcnow()
    user_dict["updated_at"] = datetime.utcnow()
    
    await db.users.insert_one(user_dict)
    
    # Return the created user
    return await get_user_by_id(x_user_id)

@router.put("/{user_id}")
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Update a user (only the user themselves can update their profile)"""
    db = await get_database()
    
    # Validate Clerk user ID from header
    if not x_user_id or len(x_user_id.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID from header"
        )
    
    # Find user by string ID first (Clerk ID), then by ObjectId if needed
    user = await db.users.find_one({"_id": user_id})
    if not user and ObjectId.is_valid(user_id):
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Only allow users to update their own profile
    # Convert both IDs to string for comparison
    actual_user_id = str(user["_id"])
    if actual_user_id != x_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own profile"
        )
    
    # Check if new email already exists (if being updated)
    if user_update.email and user_update.email != user["email"]:
        existing_email = await db.users.find_one({"email": user_update.email})
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )
    
    # Check if new username already exists (if being updated)
    if user_update.username and user_update.username != user.get("username"):
        existing_username = await db.users.find_one({"username": user_update.username})
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )
    
    # Update user
    update_data = {k: v for k, v in user_update.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    
    # Use the actual user ID from the database for the update
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": update_data}
    )
    
    # Return updated user
    return await get_user_by_id(user_id)

@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    x_user_id: str = Header(..., description="User ID from Clerk (frontend)")
):
    """Delete a user (only the user themselves can delete their account)"""
    db = await get_database()
    
    # Validate Clerk user ID from header
    if not x_user_id or len(x_user_id.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID from header"
        )
    
    # Find user by string ID first (Clerk ID), then by ObjectId if needed
    user = await db.users.find_one({"_id": user_id})
    if not user and ObjectId.is_valid(user_id):
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Only allow users to delete their own account
    # Convert both IDs to string for comparison
    actual_user_id = str(user["_id"])
    if actual_user_id != x_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own account"
        )
    
    # Delete user and all related content
    await db.users.delete_one({"_id": user["_id"]})
    
    # Also delete user's blogs and community posts (using string representation of user ID)
    await db.blogs.delete_many({"author_id": actual_user_id})
    await db.community_posts.delete_many({"author_id": actual_user_id})
    
    # Remove user from communities they're members of
    await db.communities.update_many(
        {"members": actual_user_id},
        {
            "$pull": {"members": actual_user_id},
            "$inc": {"member_count": -1}
        }
    )
    
    # Handle communities they created (transfer ownership or delete)
    # For now, we'll delete communities they created
    user_communities = await db.communities.find({"creator_id": actual_user_id}).to_list(None)
    for community in user_communities:
        community_id = str(community["_id"])
        # Delete all posts in the community
        await db.community_posts.delete_many({"community_id": community_id})
        # Delete the community
        await db.communities.delete_one({"_id": community["_id"]})
    
    return {"message": "User account and all associated data deleted successfully"}

async def _get_profile_data(user_id: str, db):
    """Helper function to get profile data for a given user ID"""
    # Find user by string ID first (Clerk ID), then by ObjectId if needed
    user = await db.users.find_one({"_id": user_id})
    
    if not user and ObjectId.is_valid(user_id):
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get the actual user ID for database queries
    actual_user_id = str(user["_id"])
    
    # Calculate user statistics
    blogs_count = await db.blogs.count_documents({"author_id": actual_user_id})
    
    # Calculate total upvotes received on user's blogs
    upvotes_pipeline = [
        {"$match": {"author_id": actual_user_id}},
        {"$group": {"_id": None, "total_upvotes": {"$sum": "$upvotes"}}}
    ]
    upvotes_result = await db.blogs.aggregate(upvotes_pipeline).to_list(1)
    total_upvotes = upvotes_result[0]["total_upvotes"] if upvotes_result else 0
    
    # Count communities user is a member of
    communities_count = await db.communities.count_documents({"members": actual_user_id})
    
    # Count communities user created
    created_communities_count = await db.communities.count_documents({"creator_id": actual_user_id})
    
    # Calculate score (can be customized based on your scoring logic)
    score = (blogs_count * 10) + (total_upvotes * 5) + (communities_count * 2) + (created_communities_count * 15)
    
    # Get recent blogs (latest 3)
    recent_blogs = await db.blogs.find({"author_id": actual_user_id})\
        .sort("created_at", -1)\
        .limit(3)\
        .to_list(3)
    
    # Format recent blogs
    for blog in recent_blogs:
        blog["created_at"] = format_timestamp(blog["created_at"])
    
    # Get recent communities (latest 3 where user is a member)
    recent_communities = await db.communities.find({"members": actual_user_id})\
        .sort("created_at", -1)\
        .limit(3)\
        .to_list(3)
    
    # Format recent communities
    for community in recent_communities:
        community["created_at"] = format_timestamp(community["created_at"])
        community["user_role"] = "admin" if community["creator_id"] == actual_user_id else "member"
    
    # Build comprehensive profile data
    profile_data = {
        "user": {
            "id": actual_user_id,
            "name": user["name"],
            "username": user.get("username", ""),
            "email": user["email"],
            "bio": user.get("bio", ""),
            "avatar": user.get("avatar", ""),
            "created_at": format_timestamp(user["created_at"]),
            "updated_at": format_timestamp(user.get("updated_at", user["created_at"]))
        },
        "stats": {
            "blogs": blogs_count,
            "upvotes": total_upvotes,
            "followers": 0,  # Placeholder for future followers feature
            "score": score,
            "communities": communities_count,
            "created_communities": created_communities_count
        },
        "recent_activity": {
            "blogs": convert_objectid_to_str(recent_blogs),
            "communities": convert_objectid_to_str(recent_communities)
        },
        "achievements": user.get("achievements", []),  # Placeholder for future achievements
        "preferences": {
            "email_notifications": True,  # Placeholder for future preferences
            "public_profile": True
        }
    }
    
    return profile_data

@router.get("/{user_id}/blogs")
async def get_user_blogs(
    user_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50)
):
    """Get all blogs by a specific user"""
    db = await get_database()
    
    # Find user by string ID first (Clerk ID), then by ObjectId if needed
    user = await db.users.find_one({"_id": user_id})
    if not user and ObjectId.is_valid(user_id):
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    skip = (page - 1) * per_page
    
    # Use the actual user ID from database for queries
    actual_user_id = str(user["_id"])
    
    # Get user's blogs
    blogs = await db.blogs.find({"author_id": actual_user_id})\
        .sort("created_at", -1)\
        .skip(skip)\
        .limit(per_page)\
        .to_list(per_page)
    
    total_count = await db.blogs.count_documents({"author_id": actual_user_id})
    
    # Add author info and format timestamps
    for blog in blogs:
        blog["author"] = {
            "id": actual_user_id,
            "name": user["name"],
            "username": user.get("username", ""),
            "avatar": user.get("avatar", ""),
            "bio": user.get("bio", "")
        }
        blog["created_at"] = format_timestamp(blog["created_at"])
    
    return {
        "blogs": convert_objectid_to_str(blogs),
        "total": total_count,
        "page": page,
        "per_page": per_page,
        "author": {
            "id": actual_user_id,
            "name": user["name"],
            "username": user.get("username", ""),
            "avatar": user.get("avatar", ""),
            "bio": user.get("bio", "")
        }
    }

@router.get("/{user_id}/communities")
async def get_user_communities(
    user_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    membership_type: Optional[str] = Query(None, regex="^(created|joined|all)$")
):
    """Get communities associated with a user (created or joined)"""
    db = await get_database()
    
    # Find user by string ID first (Clerk ID), then by ObjectId if needed
    user = await db.users.find_one({"_id": user_id})
    if not user and ObjectId.is_valid(user_id):
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    skip = (page - 1) * per_page
    
    # Use the actual user ID from database for queries
    actual_user_id = str(user["_id"])
    
    # Build filter based on membership type
    if membership_type == "created":
        filter_query = {"creator_id": actual_user_id}
    elif membership_type == "joined":
        filter_query = {"members": actual_user_id, "creator_id": {"$ne": actual_user_id}}
    else:  # "all" or None
        filter_query = {"members": actual_user_id}
    
    communities = await db.communities.find(filter_query)\
        .sort("created_at", -1)\
        .skip(skip)\
        .limit(per_page)\
        .to_list(per_page)
    
    total_count = await db.communities.count_documents(filter_query)
    
    # Add user's role in each community and format timestamps
    for community in communities:
        community["user_role"] = "admin" if community["creator_id"] == actual_user_id else "member"
        community["created_at"] = format_timestamp(community["created_at"])
    
    return {
        "communities": convert_objectid_to_str(communities),
        "total": total_count,
        "page": page,
        "per_page": per_page,
        "user": {
            "id": actual_user_id,
            "name": user["name"],
            "username": user.get("username", "")
        },
        "membership_type": membership_type or "all"
          } 