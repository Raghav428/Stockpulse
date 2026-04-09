from pydantic import BaseModel, Field, EmailStr, ConfigDict, model_validator
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


class UserLogin(BaseModel):
    email : EmailStr
    password : str


class WatchlistCreate(BaseModel):
    name : str = Field(min_length=1, max_length=50)
    

class AppendWatchlist(BaseModel):
    symbol : str = Field(min_length=1, max_length=5)


class WatchlistResponse(BaseModel):
    id: int
    name: str
    user_id: int
    symbols: list[str] = []
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode='before')
    @classmethod
    def extract_symbols(cls, data):
        if hasattr(data, 'items'):
            data.__dict__['symbols'] = [item.symbol for item in data.items]
        return data
    

class StockHistory(BaseModel):
    date: date
    symbol: str