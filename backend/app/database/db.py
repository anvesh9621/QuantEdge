import os
import time
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
from sqlalchemy.exc import OperationalError

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
        poolclass=NullPool,
        pool_pre_ping=True,
        connect_args={
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
            "connect_timeout": 10,
        }
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to yield database session
def get_db():
    max_attempts = 3
    for attempt in range(max_attempts):
        db = SessionLocal()
        try:
            yield db
            return
        except OperationalError as e:
            db.close()
            if 'SSL connection has been closed' in str(e) or 'connection' in str(e).lower():
                if attempt < max_attempts - 1:
                    print(f"[DB] SSL connection dropped, retrying ({attempt + 1}/{max_attempts})...")
                    time.sleep(1)
                    continue
            raise e
        finally:
            try:
                db.close()
            except Exception:
                pass  # already closed, ignore
