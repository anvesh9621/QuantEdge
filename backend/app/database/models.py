from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from app.database.db import Base

class StockData(Base):
    __tablename__ = "stock_data"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    date = Column(DateTime, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)

class PredictionHistory(Base):
    __tablename__ = "prediction_history"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    date = Column(DateTime, default=datetime.utcnow)
    prediction = Column(String)  # BUY, SELL, HOLD
    confidence = Column(Float)
    risk_level = Column(String)
    reasoning = Column(String)  # We can store a JSON string or comma-separated list
