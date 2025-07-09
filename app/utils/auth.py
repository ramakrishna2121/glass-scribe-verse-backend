import os
import jwt
import requests
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any

security = HTTPBearer()

class ClerkJWTError(Exception):
    """Custom exception for Clerk JWT errors"""
    pass

def get_clerk_jwks():
    """Fetch Clerk JWKS for JWT verification"""
    try:
        response = requests.get("https://api.clerk.dev/v1/jwks")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise ClerkJWTError(f"Failed to fetch Clerk JWKS: {e}")

def verify_clerk_jwt(token: str) -> Dict[str, Any]:
    """Verify Clerk JWT token and return the payload"""
    try:
        # Get the header to find the key ID
        header = jwt.get_unverified_header(token)
        kid = header.get('kid')
        
        if not kid:
            raise ClerkJWTError("Token header missing 'kid'")
        
        # Get JWKS and find the matching key
        jwks = get_clerk_jwks()
        key = None
        
        for jwk in jwks.get('keys', []):
            if jwk.get('kid') == kid:
                key = jwt.algorithms.RSAAlgorithm.from_jwk(jwk)
                break
        
        if not key:
            raise ClerkJWTError(f"Unable to find a signing key that matches: '{kid}'")
        
        # Verify and decode the token
        payload = jwt.decode(
            token,
            key,
            algorithms=['RS256'],
            audience=os.getenv('CLERK_PUBLISHABLE_KEY', ''),
            issuer=f"https://clerk.{os.getenv('CLERK_DOMAIN', 'clerk.accounts.dev')}"
        )
        
        return payload
        
    except jwt.InvalidTokenError as e:
        raise ClerkJWTError(f"Invalid token: {e}")
    except Exception as e:
        raise ClerkJWTError(f"Token verification failed: {e}")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Dependency to get current authenticated user from JWT token"""
    try:
        token = credentials.credentials
        payload = verify_clerk_jwt(token)
        
        # Extract user information from the token
        user_info = {
            "clerk_id": payload.get("sub"),
            "email": payload.get("email"),
            "name": payload.get("name", ""),
            "username": payload.get("username", ""),
            "avatar": payload.get("image_url", "")
        }
        
        if not user_info["clerk_id"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID"
            )
        
        return user_info
        
    except ClerkJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )

async def get_optional_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[Dict[str, Any]]:
    """Optional dependency to get current user - doesn't fail if no token provided"""
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None 