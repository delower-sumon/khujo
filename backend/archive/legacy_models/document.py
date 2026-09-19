from sqlalchemy import Column, Integer, String, Text, DateTime, BigInteger
from sqlalchemy.sql import func
from app.database import Base

class Document(Base):
    __tablename__ = "documents"

    id = Column(BigInteger, primary_key=True)
    url = Column(String, nullable=True)
    domain_id = Column(Integer, nullable=True)
    title = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    favicon_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    class Config:
        from_attributes = True
