from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

from app.database import connect_to_mongo, close_mongo_connection
from app.routers import users, blogs, communities, channels, auth

load_dotenv()

import firebase_admin
from firebase_admin import credentials, storage as fb_storage
import os

firebase_creds = {
    "type": os.getenv("FIREBASE_TYPE"),
    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace('\\n', '\n'),
    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.getenv("FIREBASE_CLIENT_ID"),
    "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
    "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL"),
    "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_X509_CERT_URL"),
    "universe_domain": os.getenv("FIREBASE_UNIVERSE_DOMAIN"),
}
FIREBASE_STORAGE_BUCKET = os.getenv('FIREBASE_STORAGE_BUCKET', 'your-bucket-name.appspot.com')
if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_creds)
    firebase_admin.initialize_app(cred, {'storageBucket': FIREBASE_STORAGE_BUCKET})


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongo()
    
    # Initialize categories in database
    from app.routers.communities import initialize_categories
    await initialize_categories()
    
    # Initialize blog categories in database
    from app.routers.blogs import seed_default_blog_categories
    from app.database import get_database
    db = await get_database()
    blog_categories_count = await db.blog_categories.count_documents({"is_active": True})
    if blog_categories_count == 0:
        await seed_default_blog_categories(db)
        print("✅ Blog categories initialized successfully")
    else:
        print(f"✅ Found {blog_categories_count} existing blog categories")
    
    print("🚀 Server started successfully!")
    yield
    # Shutdown
    await close_mongo_connection()

app = FastAPI(
    title="Glass Scribe Verse API",
    description="Backend API for Glass Scribe Verse - A blog and community platform (No Auth)",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",  # Frontend URL (your actual frontend port)
        "http://localhost:8081",  # Alternative frontend port
        "http://localhost:3000",  # React default port  
        "http://localhost:5173",  # Vite default port
        "http://localhost:8000",  # Backend URL (for docs)
        # Add other origins as needed
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(blogs.router, prefix="/api/blogs", tags=["blogs"])
app.include_router(communities.router, prefix="/api/communities", tags=["communities"])
app.include_router(channels.router, prefix="/api/communities", tags=["channels"])

@app.get("/")
async def root():
    return {"message": "Glass Scribe Verse API is running!"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="localhost", 
        port=int(os.getenv("PORT", 8000)), 
        reload=True
    ) 