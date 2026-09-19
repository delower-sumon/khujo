from sqlalchemy import Column, Integer, String, Text
from app.database import Base

class TransliterationMap(Base):
    __tablename__ = "transliteration_map"

    id = Column(Integer, primary_key=True)
    bangla = Column(String, nullable=True)
    english = Column(String, nullable=True)
    
    class Config:
        from_attributes = True
