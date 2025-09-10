from fastapi import APIRouter, HTTPException, status, Header, Request
from app.database import get_database
from typing import Dict, Any, Optional
from bson import ObjectId
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class AuthVerifyRequest(BaseModel):
    user_id: Optional[str] = None
    name: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None

@router.post("/verify")
async def verify_auth(
    request: Request,
    x_user_id: Optional[str] = Header(None, description="User ID from Clerk (frontend)")
):
    """Verify user authentication (placeholder endpoint for frontend)"""
    db = await get_database()
    
    # Try to get user ID from header first, then from request body
    user_id = x_user_id
    user_data = {}
    
    if not user_id:
        try:
            body = await request.json()
            user_id = body.get("user_id")
            user_data = body
        except:
            pass
    
    # Validate user ID format
    if not user_id or len(user_id.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User ID is required in header (X-User-ID) or request body"
        )
    
    # Check if user exists in database
    user = await db.users.find_one({"_id": user_id})
    if not user and ObjectId.is_valid(user_id):
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        # Auto-create user if they don't exist
        # Extract user data from request body or use defaults
        name = user_data.get("name", f"User {user_id[:8]}")
        username = user_data.get("username", f"user_{user_id[:8]}")
        email = user_data.get("email", f"{user_id}@example.com")
        
        # Create user document
        new_user = {
            "_id": user_id,
            "name": name,
            "username": username,
            "email": email,
            "bio": "",
            "avatar": "",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Insert user into database
        await db.users.insert_one(new_user)
        
        return {
            "verified": True,
            "user_id": user_id,
            "user_exists": False,
            "user_created": True,
            "message": "User automatically created"
        }
    
    return {
        "verified": True,
        "user_id": user_id,
        "user_exists": True,
        "user_created": False
    }
