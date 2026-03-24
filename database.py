#from dotenv import load_dotenv # Not needed with Docker Compose
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import declarative_base

Base = declarative_base()
#load_dotenv() #Unnecessary(Docker Compose injects .env vars into the environment)


pg_password = os.getenv("POSTGRES_PASSWORD")
if pg_password:
    DATABASE_URL = f"postgresql+asyncpg://postgres:{pg_password}@my_postgres:5432/stockpulse"

else:
    raise RuntimeError("POSTGRES_PASSWORD environment variable not set")

ALEMBIC_DATABASE_URL = f"postgresql://postgres:{pg_password}@my_postgres:5432/stockpulse"   

engine = create_async_engine(DATABASE_URL)

