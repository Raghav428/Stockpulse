from fastapi import FastAPI
from app.core.database import engine
from contextlib import asynccontextmanager
from app.api.register import router as auth_router
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
app.include_router(auth_router)

