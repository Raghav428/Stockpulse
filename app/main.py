from fastapi import FastAPI, Path, Request
from app.core.database import AsyncSessionLocal, engine
from contextlib import asynccontextmanager
from sqlalchemy import text



@asynccontextmanager
async def lifespan(app: FastAPI):

    app.state.db = AsyncSessionLocal
    yield
    await engine.dispose()



app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health(request: Request):
    async with request.app.state.db() as session:
        await session.execute(text("SELECT 1"))
    return {"status" : "ok"}

@app.get("/stock/{symbol}")
async def stock(symbol : str = Path(min_length=1, max_length=5, pattern= r"^[A-Z]+$")):
    return {
        "symbol" : symbol,
        "price" : 3*int(len(symbol)) + 2,
        "date_listed" : "23/01/2003"

    }