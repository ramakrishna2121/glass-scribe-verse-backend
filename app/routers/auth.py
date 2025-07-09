from fastapi import APIRouter, Depends, HTTPException, status
from app.utils.auth import get_current_user
from app.database import get_database
from app.models.user import User, UserCreate
from app.utils.helpers import convert_objectid_to_str
from typing import Dict, Any

router = APIRouter()

@router.post("/verify")
async def verify_token(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Verify the Clerk JWT token and return user info"""
    db = await get_database()
    
    # Check if user exists in our database
    existing_user = await db.users.find_one({"clerk_id": current_user["clerk_id"]})
    
    if not existing_user:
        # Create new user if doesn't exist
        new_user_data = UserCreate(
            name=current_user.get("name", ""),
            username=current_user.get("username", ""),
            email=current_user.get("email", ""),
            bio="",
            avatar=current_user.get("avatar", ""),
            clerk_id=current_user["clerk_id"]
        )
        
        user_dict = new_user_data.dict()
        result = await db.users.insert_one(user_dict)
        
        # Fetch the created user
        created_user = await db.users.find_one({"_id": result.inserted_id})
        user_response = convert_objectid_to_str(created_user)
    else:
        user_response = convert_objectid_to_str(existing_user)
    
    return {
        "message": "Token verified successfully",
        "user": user_response
    }

@router.get("/me")
async def get_current_user_profile(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get current user's profile"""
    db = await get_database()
    
    user = await db.users.find_one({"clerk_id": current_user["clerk_id"]})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return convert_objectid_to_str(user) 