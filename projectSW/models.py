# models.py
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from db import Base

class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, index=True)
    status = Column(String, default="PENDING")      # PENDING/PROCESSING/DONE/ERROR
    src_path = Column(String)                       # 업로드 원본 파일 경로
    result_path = Column(String, nullable=True)     # 결과 파일 경로
    error = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
