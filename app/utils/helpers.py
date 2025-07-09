from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from math import ceil

def format_timestamp(dt: datetime) -> str:
    """Format datetime to human-readable timestamp like '2 days ago'"""
    now = datetime.utcnow()
    diff = now - dt
    
    if diff.days > 7:
        return dt.strftime("%B %d, %Y")
    elif diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        return "Just now"

def create_pagination_info(
    total_items: int,
    page: int,
    per_page: int
) -> Dict[str, Any]:
    """Create pagination information"""
    total_pages = ceil(total_items / per_page)
    has_next = page < total_pages
    has_prev = page > 1
    
    return {
        "total_items": total_items,
        "total_pages": total_pages,
        "current_page": page,
        "per_page": per_page,
        "has_next": has_next,
        "has_prev": has_prev
    }

def search_filter(items: List[Dict[str, Any]], query: str, fields: List[str]) -> List[Dict[str, Any]]:
    """Filter items based on search query in specified fields"""
    if not query:
        return items
    
    query_lower = query.lower()
    filtered_items = []
    
    for item in items:
        for field in fields:
            field_value = item.get(field, "")
            if isinstance(field_value, str) and query_lower in field_value.lower():
                filtered_items.append(item)
                break
    
    return filtered_items

def sanitize_html(content: str) -> str:
    """Basic HTML sanitization - in production, use a proper library like bleach"""
    # This is a basic implementation - use bleach or similar library in production
    import re
    
    # Allow basic HTML tags
    allowed_tags = ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']
    
    # Remove script tags and their content
    content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove dangerous attributes
    content = re.sub(r'on\w+="[^"]*"', '', content, flags=re.IGNORECASE)
    content = re.sub(r"on\w+='[^']*'", '', content, flags=re.IGNORECASE)
    
    return content

def convert_objectid_to_str(obj: Any) -> Any:
    """Convert MongoDB ObjectId to string in nested objects"""
    from bson import ObjectId
    
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, dict):
        return {key: convert_objectid_to_str(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_objectid_to_str(item) for item in obj]
    else:
        return obj 