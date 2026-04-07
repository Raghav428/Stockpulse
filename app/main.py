from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import engine, get_db
from contextlib import asynccontextmanager
from app.api.register import router as auth_router
from app.api.watchlists import router as watchlists_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()

app = FastAPI(lifespan=lifespan)

app.include_router(auth_router)
app.include_router(watchlists_router)


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(1))
    
    if result:
        return {'status' : 'healthy'}
