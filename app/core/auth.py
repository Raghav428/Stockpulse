from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from datetime import datetime, timezone
from app.core.crypto import decode_access_token
from app.core.database import get_db
from app.models.models import User



oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")



async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    
    try:
        user_id = decode_access_token(token)
    
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Credentials")
    
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Credentials")
    
    return user
    
