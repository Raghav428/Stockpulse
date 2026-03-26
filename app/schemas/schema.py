from pydantic import BaseModel, Field, EmailStr, ConfigDict
from datetime import date, datetime


class Stock(BaseModel):
    symbol : str = Field(min_length=1, max_length=5)

class UserCreate(BaseModel):
    first_name : str = Field(min_length=1, max_length=50)
    last_name : str
    DOB : date
    email : EmailStr
    password : str = Field(min_length=8)

class UserResponse(BaseModel):
    id : int
    is_active: bool
    created_at : datetime
    first_name : str
    last_name : str
    email: EmailStr
    DOB : date
    model_config = ConfigDict(from_attributes = True)