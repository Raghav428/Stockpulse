from fastapi import FastAPI, Path, Depends
from app.core.database import AsyncSessionLocal, engine, get_db
from contextlib import asynccontextmanager
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()

app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health(session: AsyncSession = Depends(get_db)):
    await session.execute(text("SELECT 1"))
    return {"status" : "ok"}

@app.get("/stock/{symbol}")
async def stock(symbol : str = Path(min_length=1, max_length=5, pattern= r"^[A-Z]+$")):
    return {
        "symbol" : symbol,
        "price" : 3*int(len(symbol)) + 2,
        "date_listed" : "23/01/2003"
    }