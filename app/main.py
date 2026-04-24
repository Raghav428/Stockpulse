from fastapi import FastAPI, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.postgresql import engine, get_db
from app.core.cassandra import connect_cassandra, close_cassandra
from contextlib import asynccontextmanager
from app.api.register import router as auth_router
from app.api.watchlists import router as watchlists_router
from app.api.historical_data import router as historical_data_router
from app.api.live_data import connect_redis, close_redis
from app.api.live_data import router as live_data_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    connect_cassandra()
    await connect_redis()
    yield
    await engine.dispose()
    close_cassandra()
    await close_redis()

app = FastAPI(lifespan=lifespan)

app.include_router(auth_router)
app.include_router(watchlists_router)
app.include_router(historical_data_router)
app.include_router(live_data_router)


@app.get("/health", status_code=status.HTTP_200_OK)
async def health(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(1))
    
    if result:
        return {'status' : 'healthy'}
