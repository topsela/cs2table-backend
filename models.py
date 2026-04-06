from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"

    steam_id = Column(String, primary_key=True, index=True)
    username = Column(String, nullable=False)
    avatar = Column(String, nullable=True)
    profile_url = Column(String, nullable=True)
    plan = Column(String, default="free")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), onupdate=func.now())