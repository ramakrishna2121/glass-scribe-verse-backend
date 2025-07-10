from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

from app.database import connect_to_mongo, close_mongo_connection
from app.routers import users, blogs, communities

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongo()
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
        "http://localhost:8081",  # Frontend URL
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
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(blogs.router, prefix="/api/blogs", tags=["blogs"])
app.include_router(communities.router, prefix="/api/communities", tags=["communities"])

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