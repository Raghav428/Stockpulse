from fastapi import FastAPI
from app.core.database import engine
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
