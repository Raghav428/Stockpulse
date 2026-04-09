from fastapi import FastAPI, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.postgresql import engine, get_db
from app.core.cassandra import connect_cassandra, close_cassandra
from contextlib import asynccontextmanager
from app.api.register import router as auth_router
from app.api.watchlists import router as watchlists_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    connect_cassandra()
    yield
    await engine.dispose()
    close_cassandra()

app = FastAPI(lifespan=lifespan)

app.include_router(auth_router)
app.include_router(watchlists_router)


@app.get("/health", status_code=status.HTTP_200_OK)
async def health(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(1))
    
    if result:
        return {'status' : 'healthy'}
