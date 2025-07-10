
# Glass Scribe Verse Backend

A FastAPI backend for a blogging and community platform with MongoDB database.

## Features

- User management system
- Blog creation and management
- Community creation and management
- Community posts
- Upvoting system
- Search functionality
- Pagination support

## Authentication

This backend is designed to work with **Clerk authentication** handled by the frontend. The frontend should:

1. Handle user authentication using Clerk
2. Pass the user ID from Clerk in the `X-User-ID` header for authenticated requests
3. Create user profiles in the backend using the Clerk user ID

### User Signup Flow

When a user signs up through Clerk:

1. **Clerk handles authentication** and provides a user ID
2. **Frontend creates user profile** in the backend using the Clerk user ID
3. **All subsequent requests** use the same Clerk user ID

### Required Header

For any authenticated requests (create, update, delete, upvote), include:

```
X-User-ID: <clerk_user_id>
```

### Example Frontend Usage

```javascript
// Frontend example - User signup flow
const handleUserSignup = async (clerkUser) => {
  // After Clerk authentication, create user profile in backend
  const userProfile = {
    name: clerkUser.fullName,
    username: clerkUser.username,
    email: clerkUser.emailAddresses[0].emailAddress,
    bio: "",
    avatar: clerkUser.imageUrl
  };
  
  const response = await fetch('/api/users', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-ID': clerkUser.id  // Clerk user ID
    },
    body: JSON.stringify(userProfile)
  });
  
  return response.json();
};

// Frontend example - Creating a blog post
const createBlog = async (blogData) => {
  const userID = auth.userId; // From Clerk
  
  const response = await fetch('/api/blogs', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-ID': userID
    },
    body: JSON.stringify(blogData)
  });
  
  return response.json();
};
```

## Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd glass-scribe-verse-backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the root directory:
   ```env
   MONGODB_URL=mongodb+srv://username:password@cluster.mongodb.net/glass_scribe_verse?retryWrites=true&w=majority&tlsAllowInvalidCertificates=true
   ```

5. **Run the server**
   ```bash
   python main.py
   ```

The server will start on `http://0.0.0.0:8000`

## API Documentation

Once the server is running, visit:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## API Endpoints

### Users
- `GET /api/users` - Get all users with pagination and search
- `GET /api/users/{user_id}` - Get specific user
- `POST /api/users` - Create new user (requires X-User-ID header with Clerk user ID)
- `PUT /api/users/{user_id}` - Update user (requires X-User-ID header)
- `DELETE /api/users/{user_id}` - Delete user (requires X-User-ID header)
  - `GET /api/users/profile` - Get current user's profile with stats (requires X-User-ID header)
  - `GET /api/users/me/profile` - Alternative endpoint for current user's profile (requires X-User-ID header)
- `GET /api/users/{user_id}/blogs` - Get user's blogs
- `GET /api/users/{user_id}/communities` - Get user's communities

### Blogs
- `GET /api/blogs` - Get all blogs with pagination and filtering
- `GET /api/blogs/search` - Search blogs
- `GET /api/blogs/{blog_id}` - Get specific blog
- `POST /api/blogs` - Create new blog (requires X-User-ID header)
- `PUT /api/blogs/{blog_id}` - Update blog (requires X-User-ID header)
- `DELETE /api/blogs/{blog_id}` - Delete blog (requires X-User-ID header)
- `POST /api/blogs/{blog_id}/upvote` - Toggle upvote (requires X-User-ID header)

### Communities
- `GET /api/communities` - Get all communities
- `GET /api/communities/{community_id}` - Get specific community
- `POST /api/communities` - Create new community (requires X-User-ID header)
- `PUT /api/communities/{community_id}` - Update community (requires X-User-ID header)
- `DELETE /api/communities/{community_id}` - Delete community (requires X-User-ID header)
- `POST /api/communities/{community_id}/join` - Join community (requires X-User-ID header)
- `POST /api/communities/{community_id}/leave` - Leave community (requires X-User-ID header)
- `GET /api/communities/{community_id}/members` - Get community members
- `GET /api/communities/{community_id}/posts` - Get community posts
- `POST /api/communities/{community_id}/posts` - Create community post (requires X-User-ID header)
- `PUT /api/communities/{community_id}/posts/{post_id}` - Update community post (requires X-User-ID header)
- `DELETE /api/communities/{community_id}/posts/{post_id}` - Delete community post (requires X-User-ID header)
- `POST /api/communities/{community_id}/posts/{post_id}/upvote` - Toggle upvote on community post (requires X-User-ID header)

### Profile Endpoints

#### Get User Profile
```
GET /api/users/profile
Headers: X-User-ID: {clerk_user_id}
```
Get comprehensive profile data for the authenticated user including statistics, recent activity, and user information.

**Response:**
```json
{
  "user": {
    "id": "user_2wjPPZP4QCLBdJfcF4O638Y2zd7",
    "name": "John Doe",
    "username": "johndoe",
    "email": "john@example.com",
    "bio": "Software developer",
    "avatar": "https://example.com/avatar.jpg",
    "created_at": "Dec 15, 2024 10:30 AM",
    "updated_at": "Dec 15, 2024 02:45 PM"
  },
  "stats": {
    "blogs": 5,
    "upvotes": 24,
    "followers": 0,
    "score": 170,
    "communities": 3,
    "created_communities": 1
  },
  "recent_activity": {
    "blogs": [...],
    "communities": [...]
  },
  "achievements": [],
  "preferences": {
    "email_notifications": true,
    "public_profile": true
  }
}
```

#### Get Current User Profile (Alternative)
```
GET /api/users/me/profile
Headers: X-User-ID: {clerk_user_id}
```
Alternative endpoint for getting the current user's profile (same functionality as `/profile`).

## Database Structure

The application uses MongoDB with the following collections:
- `users` - User profiles
- `blogs` - Blog posts
- `communities` - Community information
- `community_posts` - Posts within communities

## Technology Stack

- **FastAPI** - Web framework
- **MongoDB** - Database
- **Motor** - Async MongoDB driver
- **Pydantic** - Data validation
- **uvicorn** - ASGI server

## Project Structure

```
glass-scribe-verse-backend/
├── app/
│   ├── models/          # Pydantic models
│   ├── routers/         # API route handlers
│   ├── utils/           # Utility functions
│   └── database.py      # Database connection
├── main.py              # Application entry point
├── requirements.txt     # Dependencies
└── README.md           # This file
```

