from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from backend.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=30,        # P1-10: handle 100 concurrent students
    max_overflow=50,
    pool_timeout=30,
    pool_pre_ping=True,  # detect stale connections
)

AsyncSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
