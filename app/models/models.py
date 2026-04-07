from app.core.database import Base
from sqlalchemy import Column, String, Integer, DateTime, Date, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func


class User(Base):
    __tablename__ = "Users"

    id = Column(Integer, primary_key=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=True)
    DOB = Column(Date, nullable=False)
    email = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)


class Watchlist(Base):
    __tablename__ = "Watchlists"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("Users.id"), nullable=False)
    items = relationship("WatchlistItem", back_populates="watchlist")
    

class WatchlistItem(Base):
    __tablename__ = "WatchlistItems"
    
    id = Column(Integer, primary_key=True)
    watchlist_id = Column(Integer, ForeignKey("Watchlists.id"), nullable=False)
    symbol = Column(String, nullable=False)
    watchlist = relationship("Watchlist", back_populates="items")
    __table_args__ = (
        UniqueConstraint("watchlist_id", "symbol", name="uq_watchlist_item"),
    )

from pydantic import BaseModel, model_validator, ConfigDict

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