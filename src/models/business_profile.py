from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, Float, JSON, Boolean
from src.models.base import Base


class BusinessProfile(Base):
    __tablename__ = "business_profiles"

    user_id = Column(String(32), primary_key=True)
    business_name = Column(String(255), default="")
    industry = Column(String(128), default="")
    revenue_range = Column(String(128), default="")
    team_size = Column(String(64), default="")
    location = Column(String(255), default="")
    pain_points = Column(Text, default="")
    goals = Column(Text, default="")
    phone = Column(String(32), default="")
    raw_data = Column(JSON, default=dict)
    intake_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Fix #9: Use lambda to ensure fresh timestamp on each update
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=lambda: datetime.utcnow())
