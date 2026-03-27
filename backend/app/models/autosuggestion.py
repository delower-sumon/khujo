from sqlalchemy import Column, Integer, String, Text, Boolean, Numeric, TIMESTAMP
from sqlalchemy.sql import func
from app.database import Base

class Autosuggestion(Base):
    __tablename__ = "autosuggestions"

    id = Column(Integer, primary_key=True)
    phrase = Column(Text, nullable=False)
    transliteration = Column(Text, nullable=True)
    language_code = Column(String(10), nullable=True)
    category = Column(String(50), nullable=True)
    search_volume_weight = Column(Numeric(3, 2), nullable=True)
    intent = Column(String(20), nullable=True)
    is_trending = Column(Boolean, default=False)
    priority_level = Column(Integer, default=1)
    source_type = Column(String(20), default='curated')
    created_at = Column(TIMESTAMP, server_default=func.now())

    class Config:
        from_attributes = True
