from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.core.config import settings

# Create async engine tuned for AWS RDS
# pool_pre_ping=True: tests the connection before use — critical for RDS
#   which drops idle connections after a timeout period.
# pool_size / max_overflow: limits max concurrent DB connections.
engine = create_async_engine(
    settings.database_url,
    echo=False,          # Set to True for debugging SQL queries
    future=True,
    pool_pre_ping=True,  # Detects and recovers from dropped RDS connections
    pool_size=10,        # Max persistent connections in the pool
    max_overflow=20,     # Max extra connections allowed under heavy load
    pool_recycle=1800,   # Recycle connections every 30 min (before RDS drops them)
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

async def get_db():
    """Dependency for getting async database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
