from app.core.database import Base
from sqlalchemy import Column, String, Integer, DateTime, Date, Boolean
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