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
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb+srv://sattiramakrishna333:3imKhVRLVax7Y2GX@scribe.vphq5bz.mongodb.net/")
    database_name = os.getenv("DATABASE_NAME", "glass_scribe_verse")
    
    db.client = AsyncIOMotorClient(
        mongodb_uri,
        server_api=ServerApi('1'),
        tlsAllowInvalidCertificates=True  # Bypass SSL certificate verification
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