import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

Base = declarative_base()

### PostgreSQL password loading
pg_password = os.getenv("POSTGRES_PASSWORD")

if pg_password:
    DATABASE_URL = f"postgresql+asyncpg://postgres:{pg_password}@my_postgres:5432/stockpulse"
else:
    raise RuntimeError("POSTGRES_PASSWORD environment variable not set")
###

#Sync Database URL for migrations
ALEMBIC_DATABASE_URL = f"postgresql://postgres:{pg_password}@my_postgres:5432/stockpulse"   
#Async engine
engine = create_async_engine(DATABASE_URL)
#Async session factory
AsyncSessionLocal = async_sessionmaker(engine, class_= AsyncSession, expire_on_commit=False)



async def get_db():
    async with AsyncSessionLocal() as session:
        yield session