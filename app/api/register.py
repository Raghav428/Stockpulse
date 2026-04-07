from fastapi import APIRouter, HTTPException, status
from app.schemas.schema import UserCreate, UserResponse, UserLogin
from app.models.models import User
from sqlalchemy import select
from app.core.database import get_db
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.crypto import hash_password, verify_password, create_access_token
from app.core.auth import get_current_user


router = APIRouter(prefix = '/api/v1/auth')



@router.post("/register")
async def register_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
   
    existing =  ( await
            db.execute(select(User)
            .where(User.email == user_data.email)
            )).scalar_one_or_none()

    
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Registration failed!"
        )

    hashed_password = hash_password(user_data.password) ###filler function

    user = User(
        email = user_data.email,
        hashed_password = hashed_password,
        is_active = True,
        DOB = user_data.DOB,
        first_name = user_data.first_name,
        last_name = user_data.last_name
        )

    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.get("/users/me")
async def get_user_data(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)

    
@router.get("/users/{id}")
async def fetch_user(id: int, db: AsyncSession = Depends(get_db)):
   
    user =  ( await
            db.execute(select(User)
            .where(User.id == id)
            )).scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User Not Found"
        )        

    return UserResponse.model_validate(user)


@router.post("/login")
async def login(user_data: UserLogin, db: AsyncSession = Depends(get_db)):

    existing =  ( 
            await db.execute(select(User)
            .where(User.email == user_data.email)
            )).scalar_one_or_none()

    if not existing:
        raise HTTPException(status_code=401, detail="Invalid Credentials")

    is_valid, new_hash = verify_password(user_data.password, existing.hashed_password)

    if is_valid:
        
        if new_hash:
            existing.hashed_password = new_hash
            await db.commit()
            await db.refresh(existing)
        
        token = create_access_token(existing.id)
        
        return {"token":str(token), "token_type": "bearer"}

    else:
        raise HTTPException(status_code=401, detail="Invalid Credentials")


