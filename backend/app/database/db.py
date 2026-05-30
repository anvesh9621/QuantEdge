from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Use SQLite as a fallback if DATABASE_URL is not provided
# For PostgreSQL the url format is: postgresql://user:password@localhost/dbname
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./stock_market.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# create_engine expects special arguments for SQLite
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # pool_pre_ping=True: tests connection health before use — fixes Neon's
    # serverless SSL drops ("SSL connection has been closed unexpectedly").
    # pool_recycle=300: recycles connections every 5 min to prevent stale ones.
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to yield database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
