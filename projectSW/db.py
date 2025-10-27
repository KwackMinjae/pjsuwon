# db.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# .env 불러오기
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# DB 엔진/세션 설정
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 요청마다 DB 세션 열고 닫기
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
