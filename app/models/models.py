from app.core.database import Base
from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.sql import func



class User(Base):
    __tablename__ = "Users"

    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())