# Community Creation API Guide

This guide provides all the APIs needed to support your community creation form as shown in the frontend screenshots.

## 🔧 Required Headers

All authenticated endpoints require:
```
X-User-ID: {clerk_user_id}
Content-Type: application/json
```

---

## 📷 Image Upload APIs

### Upload Community Logo
```http
POST /api/communities/upload/logo
Content-Type: multipart/form-data
Headers: X-User-ID: {clerk_user_id}

Form Data:
- file: (image file, max 5MB, JPEG/PNG/JPG/WebP)
```

**Response:**
```json
{
  "url": "/uploads/community/logos/abc123.jpg",
  "filename": "abc123.jpg",
  "size": 1048576
}
```

### Upload Community Cover Image
```http
POST /api/communities/upload/cover
Content-Type: multipart/form-data
Headers: X-User-ID: {clerk_user_id}

Form Data:
- file: (image file, max 10MB, JPEG/PNG/JPG/WebP)
```

**Response:**
```json
{
  "url": "/uploads/community/covers/def456.jpg",
  "filename": "def456.jpg",
  "size": 2097152
}
```

---

## 📂 Category Management APIs

**Database-Backed System**: Categories are now stored in MongoDB and automatically seeded with 20 default categories on server startup.

### Get Available Categories (Simple List)
```http
GET /api/communities/categories
```

**Response:**
```json
{
  "categories": [
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
}
```

### Get Detailed Categories with Community Counts
```http
GET /api/communities/categories/detailed
```

**Response:**
```json
{
  "categories": [
    {
      "id": "674a1b2c3d4e5f6789012345",
      "name": "Technology",
      "slug": "technology",
      "description": "Communities focused on technology",
      "community_count": 25,
      "is_default": true,
      "created_at": "1 week ago"
    },
    {
      "id": "674a1b2c3d4e5f6789012346",
      "name": "Programming",
      "slug": "programming",
      "description": "Communities focused on programming",
      "community_count": 18,
      "is_default": true,
      "created_at": "1 week ago"
    }
  ]
}
```

### Get Category by Slug
```http
GET /api/communities/categories/{category_slug}
```

**Response:**
```json
{
  "id": "674a1b2c3d4e5f6789012345",
  "name": "Technology",
  "slug": "technology",
  "description": "Communities focused on technology",
  "community_count": 25,
  "is_default": true,
  "created_at": "1 week ago"
}
```

### Add Custom Category
```http
POST /api/communities/categories?category_name={name}&description={description}
Headers: X-User-ID: {clerk_user_id}
```

**Response:**
```json
{
  "message": "Category added successfully",
  "category": {
    "id": "674a1b2c3d4e5f6789012347",
    "name": "Web3",
    "slug": "web3",
    "description": "Communities focused on web3"
  }
}
```

### Update Category
```http
PUT /api/communities/categories/{category_id}?name={new_name}&description={new_description}
Headers: X-User-ID: {clerk_user_id}
```

### Delete Category
```http
DELETE /api/communities/categories/{category_id}
Headers: X-User-ID: {clerk_user_id}
```

**Note**: Categories with existing communities cannot be deleted.

### Recalculate Category Counts (Admin)
```http
POST /api/communities/categories/recalculate-counts
Headers: X-User-ID: {clerk_user_id}
```

**Response:**
```json
{
  "message": "Recalculated counts for 3 categories",
  "total_categories": 21,
  "updated_categories": 3
}
```

---

## 🏘️ Community Creation & Management APIs

### Create Community
```http
POST /api/communities
Headers: X-User-ID: {clerk_user_id}
Content-Type: application/json
```

**Request Body:**
```json
{
  "name": "Python Development",
  "description": "Learn python in 50 days.",
  "access_type": "free",  // "free", "invite", "paid"
  "price": null,  // Required if access_type is "paid"
  "categories": ["Technology", "Programming"],
  "logo_url": "/uploads/community/logos/abc123.jpg",  // From upload API
  "cover_image_url": "/uploads/community/covers/def456.jpg",  // From upload API
  "custom_domain": "python.yourdomain.com",  // Optional
  "settings": {
    "enable_member_posts": true,
    "enable_comments": true,
    "enable_upvotes": true,
    "show_members_publicly": true,
    "require_approval_for_posts": false,
    "require_approval_for_members": false
  }
}
```

**Response:**
```json
{
  "id": "674a1b2c3d4e5f6789012345",
  "name": "Python Development",
  "description": "Learn python in 50 days.",
  "logo_url": "/uploads/community/logos/abc123.jpg",
  "cover_image_url": "/uploads/community/covers/def456.jpg",
  "member_count": 1,
  "access_type": "free",
  "price": null,
  "categories": ["Technology", "Programming"],
  "custom_domain": "python.yourdomain.com",
  "settings": {
    "enable_member_posts": true,
    "enable_comments": true,
    "enable_upvotes": true,
    "show_members_publicly": true,
    "require_approval_for_posts": false,
    "require_approval_for_members": false
  },
  "created_at": "2 minutes ago",
  "is_joined": true,
  "user_role": "admin"
}
```

### Get All Communities
```http
GET /api/communities?page=1&per_page=10&access_type=free&category=Technology
```

**Response:**
```json
{
  "communities": [
    {
      "id": "674a1b2c3d4e5f6789012345",
      "name": "Python Development",
      "description": "Learn python in 50 days.",
      "logo_url": "/uploads/community/logos/abc123.jpg",
      "cover_image_url": "/uploads/community/covers/def456.jpg",
      "member_count": 150,
      "access_type": "free",
      "categories": ["Technology", "Programming"],
      "created_at": "2 days ago"
    }
  ],
  "total": 50,
  "page": 1,
  "per_page": 10
}
```

### Get Community Details
```http
GET /api/communities/{community_id}
```

### Update Community
```http
PUT /api/communities/{community_id}
Headers: X-User-ID: {clerk_user_id}
Content-Type: application/json

Body: (same as create, all fields optional)
```

### Delete Community
```http
DELETE /api/communities/{community_id}
Headers: X-User-ID: {clerk_user_id}
```

---

## 👥 Community Membership APIs

### Join Community (Free)
```http
POST /api/communities/{community_id}/join
Headers: X-User-ID: {clerk_user_id}
```

### Join Community by Invite Code
```http
POST /api/communities/join-by-invite?invite_code={code}
Headers: X-User-ID: {clerk_user_id}
```

**Response:**
```json
{
  "message": "Successfully joined Python Development",
  "community": {
    "id": "674a1b2c3d4e5f6789012345",
    "name": "Python Development",
    "description": "Learn python in 50 days."
  }
}
```

### Leave Community
```http
POST /api/communities/{community_id}/leave
Headers: X-User-ID: {clerk_user_id}
```

### Get Community Members
```http
GET /api/communities/{community_id}/members?page=1&per_page=20
```

**Response:**
```json
{
  "members": [
    {
      "id": "user_2wjPPZP4QCLBdJfcF4O638Y2zd7",
      "name": "John Doe",
      "username": "johndoe",
      "avatar": "https://img.clerk.com/...",
      "role": "admin",
      "post_count": 5,
      "joined_at": "1 week ago"
    }
  ],
  "total": 150,
  "page": 1,
  "per_page": 20
}
```

---

## 🎟️ Invite Management APIs (For Invite-Only Communities)

### Generate Invite Code
```http
POST /api/communities/{community_id}/invites?expires_in_hours=24&max_uses=10
Headers: X-User-ID: {clerk_user_id}
```

**Response:**
```json
{
  "invite_code": "abc123def456",
  "expires_at": "2024-07-12T14:30:00Z",
  "max_uses": 10,
  "community_name": "Python Development"
}
```

### List Community Invites
```http
GET /api/communities/{community_id}/invites
Headers: X-User-ID: {clerk_user_id}
```

**Response:**
```json
{
  "invites": [
    {
      "invite_code": "abc123def456",
      "created_at": "1 hour ago",
      "expires_at": "23 hours ago",
      "max_uses": 10,
      "current_uses": 3,
      "created_by": "user_2wjPPZP4QCLBdJfcF4O638Y2zd7"
    }
  ]
}
```

### Deactivate Invite Code
```http
DELETE /api/communities/{community_id}/invites/{invite_code}
Headers: X-User-ID: {clerk_user_id}
```

---

## 💬 Community Posts APIs

### Get Community Posts
```http
GET /api/communities/{community_id}/posts?page=1&per_page=10&post_type=discussion
```

### Create Community Post
```http
POST /api/communities/{community_id}/posts
Headers: X-User-ID: {clerk_user_id}
Content-Type: application/json
```

**Request Body:**
```json
{
  "title": "Welcome to Python Development!",
  "content": "This is our first community post...",
  "type": "announcement",  // "discussion", "announcement", "question", "poll", "link"
  "category": "General",
  "tags": ["welcome", "intro"]
}
```

### Update Community Post
```http
PUT /api/communities/{community_id}/posts/{post_id}
Headers: X-User-ID: {clerk_user_id}
```

### Delete Community Post
```http
DELETE /api/communities/{community_id}/posts/{post_id}
Headers: X-User-ID: {clerk_user_id}
```

### Toggle Post Upvote
```http
POST /api/communities/{community_id}/posts/{post_id}/upvote
Headers: X-User-ID: {clerk_user_id}
```

---

## 📝 Frontend Integration Examples

### Community Creation Form Handler

```javascript
const handleCreateCommunity = async (formData) => {
  const userID = auth.userId; // From Clerk
  
  try {
    // 1. Upload logo if provided
    let logoUrl = null;
    if (formData.logoFile) {
      const logoFormData = new FormData();
      logoFormData.append('file', formData.logoFile);
      
      const logoResponse = await fetch('/api/communities/upload/logo', {
        method: 'POST',
        headers: { 'X-User-ID': userID },
        body: logoFormData
      });
      const logoData = await logoResponse.json();
      logoUrl = logoData.url;
    }
    
    // 2. Upload cover image if provided
    let coverUrl = null;
    if (formData.coverFile) {
      const coverFormData = new FormData();
      coverFormData.append('file', formData.coverFile);
      
      const coverResponse = await fetch('/api/communities/upload/cover', {
        method: 'POST',
        headers: { 'X-User-ID': userID },
        body: coverFormData
      });
      const coverData = await coverResponse.json();
      coverUrl = coverData.url;
    }
    
    // 3. Create community
    const communityData = {
      name: formData.name,
      description: formData.description,
      access_type: formData.accessType,
      price: formData.price,
      categories: formData.categories,
      logo_url: logoUrl,
      cover_image_url: coverUrl,
      custom_domain: formData.customDomain,
      settings: {
        enable_member_posts: formData.enableMemberPosts,
        enable_comments: formData.enableComments,
        enable_upvotes: formData.enableUpvotes,
        show_members_publicly: formData.showMembersPublicly
      }
    };
    
    const response = await fetch('/api/communities', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-ID': userID
      },
      body: JSON.stringify(communityData)
    });
    
    const community = await response.json();
    console.log('Community created:', community);
    
    // Redirect to community page
    router.push(`/communities/${community.id}`);
    
  } catch (error) {
    console.error('Error creating community:', error);
  }
};
```

### Load Categories for Dropdown

```javascript
const loadCategories = async () => {
  try {
    const response = await fetch('/api/communities/categories');
    const data = await response.json();
    setCategories(data.categories);
  } catch (error) {
    console.error('Error loading categories:', error);
  }
};
```

---

## 🚨 Error Handling

Common HTTP status codes and their meanings:

- **400 Bad Request**: Invalid data format or missing required fields
- **401 Unauthorized**: Missing or invalid X-User-ID header
- **403 Forbidden**: User doesn't have permission (e.g., not community admin)
- **404 Not Found**: Community, user, or invite code not found
- **409 Conflict**: Community name or custom domain already exists

Example error response:
```json
{
  "detail": "Community name already exists"
}
```

---

## 🎯 Quick Testing

You can test these APIs using the FastAPI docs at `http://localhost:8000/docs` once your server is running.

All APIs are ready to support your community creation form! 🚀 