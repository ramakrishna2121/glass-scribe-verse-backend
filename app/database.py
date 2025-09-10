import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.server_api import ServerApi

class Database:
    client: AsyncIOMotorClient = None
    database = None

db = Database()

async def get_database():
    return db.database

async def connect_to_mongo():
    """Create database connection"""
    mongodb_uri = os.getenv("MONGODB_URI")
    database_name = os.getenv("DATABASE_NAME", "glass_scribe_verse")
    
    if not mongodb_uri:
        print("⚠️  No MONGODB_URI found in environment variables")
        return
    
    db.client = AsyncIOMotorClient(
        mongodb_uri,
        server_api=ServerApi('1'),
        connectTimeoutMS=30000,  # 30 second connection timeout
        serverSelectionTimeoutMS=30000,  # 30 second server selection timeout
        socketTimeoutMS=30000,  # 30 second socket timeout
    )
    db.database = db.client[database_name]
    
    # Test the connection
    try:
        await db.client.admin.command('ping')
        print("✅ Successfully connected to MongoDB!")
    except Exception as e:
        print(f"❌ Error connecting to MongoDB: {e}")
        raise

async def close_mongo_connection():
    """Close database connection"""
    if db.client:
        db.client.close()
        print("🔌 Disconnected from MongoDB") 