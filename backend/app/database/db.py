from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

from sqlalchemy.pool import NullPool

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
    # Disable connection pooling entirely for serverless DBs (Neon).
    # Neon aggressively drops idle connections, so pooling causes SSL drop errors
    # during long-running background ML tasks. NullPool creates fresh connections.
    engine = create_engine(
        DATABASE_URL,
        poolclass=NullPool
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
