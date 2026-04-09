from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from datetime import date as Date
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.schema import UserCreate, UserResponse
from app.models.models import User
from app.core.postgresql import get_db
from app.core.crypto import hash_password, verify_password, create_access_token
from app.core.auth import get_current_user
from app.core.cassandra import session



router = APIRouter(prefix = '/api/v1/historical_data')



@router.get("/stocks/{symbol}/history")
async def history(
    date: Date,
    symbol: str
):
    data = session.execute(
        "SELECT * FROM tick_data WHERE symbol = %s AND date = %s",
        (symbol, str(date))
        )
    
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return data.all()
    