import os
from app.database.db import SessionLocal
from app.database.models import StockData
from app.ml.train import train_model

def train_all_stocks():
    db = SessionLocal()
    # Fetch all unique stock tickers from the Postgres Database
    tickers = db.query(StockData.ticker).distinct().all()
    tickers = [t[0] for t in tickers]
    db.close()
    
    print(f"Found {len(tickers)} unique stocks. Starting bulk training...")
    
    success = 0
    for tick in tickers:
        try:
            # Trains the model, which internally fetches yfinance delta beforehand automatically
            if train_model(tick, 'rf'):
                success += 1
        except Exception as e:
            print(f"Failed to train {tick}: {e}")
            
    print(f"Bulk training complete! Successfully trained {success} out of {len(tickers)} models.")

if __name__ == "__main__":
    train_all_stocks()
