# database.py
# StockAdvisor Backend - MongoDB Database Service
# Created by Digital COE Gen AI Team

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from loguru import logger

from app.config import settings
from app.models.schemas import User, Portfolio, Watchlist, Transaction, AISignal, MarketInsight


class DatabaseService:
    """MongoDB database service using Motor and Beanie ODM."""
    
    client: AsyncIOMotorClient = None
    database = None
    
    @classmethod
    async def connect(cls):
        """Connect to MongoDB database."""
        try:
            cls.client = AsyncIOMotorClient(
                settings.MONGODB_URL,
                maxPoolSize=50,
                minPoolSize=10,
                serverSelectionTimeoutMS=5000
            )
            
            cls.database = cls.client[settings.MONGODB_DATABASE]
            
            # Initialize Beanie with document models
            await init_beanie(
                database=cls.database,
                document_models=[
                    User,
                    Portfolio,
                    Watchlist,
                    Transaction,
                    AISignal,
                    MarketInsight
                ]
            )
            
            # Create indexes
            await cls._create_indexes()
            
            logger.info(f"Connected to MongoDB: {settings.MONGODB_DATABASE}")
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    @classmethod
    async def disconnect(cls):
        """Disconnect from MongoDB database."""
        if cls.client:
            cls.client.close()
            logger.info("Disconnected from MongoDB")
    
    @classmethod
    async def check_health(cls) -> bool:
        """Check database health status."""
        try:
            await cls.client.admin.command('ping')
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    @classmethod
    async def _create_indexes(cls):
        """Create database indexes for better query performance."""
        try:
            # User indexes
            await User.get_collection().create_index("email", unique=True)
            
            # Portfolio indexes
            await Portfolio.get_collection().create_index("user_id")
            
            # Watchlist indexes
            await Watchlist.get_collection().create_index("user_id")
            
            # Transaction indexes
            await Transaction.get_collection().create_index([
                ("user_id", 1),
                ("timestamp", -1)
            ])
            
            # AI Signal indexes
            await AISignal.get_collection().create_index([
                ("stock_symbol", 1),
                ("is_active", 1)
            ])
            await AISignal.get_collection().create_index("expires_at", expireAfterSeconds=0)
            
            # Market Insight indexes
            await MarketInsight.get_collection().create_index([
                ("category", 1),
                ("published_at", -1)
            ])
            
            logger.info("Database indexes created successfully")
            
        except Exception as e:
            logger.warning(f"Index creation warning: {e}")

