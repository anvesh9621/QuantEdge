import os
import gc
import time
import random
import requests
from app.database.db import SessionLocal
from app.database.models import StockData
from app.ml.train import train_model

def train_all_stocks():
    # Log outbound IP to diagnose rate limit sources
    try:
        ip = requests.get("https://api.ipify.org", timeout=5).text
        print(f"Outbound IP Address: {ip}")
    except Exception as e:
        print(f"Failed to fetch outbound IP: {e}")
        
    DEAD_TICKERS = {'HDFC', 'HDFC.NS', 'MM', 'MM.NS'}
    
    with SessionLocal() as db:
        # Fetch all unique stock tickers from the Postgres Database
        tickers = db.query(StockData.ticker).distinct().all()
        tickers = [
            t[0] for t in tickers 
            if t[0].upper() not in DEAD_TICKERS 
            and t[0].upper().replace('.NS','') not in DEAD_TICKERS
        ]
        
    print(f"===========================================================")
    print(f"Excluded dead tickers: {DEAD_TICKERS}")
    print(f"Processing {len(tickers)} active tickers...")
    print(f"===========================================================")
    
    successes = []
    failures = []
    
    for tick in tickers:
        try:
            print(f"--- Processing {tick} ---")
            
            with SessionLocal() as db:
                # Trains the model, which internally fetches yfinance delta beforehand automatically
                result = train_model(tick, 'rf')
            
            if result and isinstance(result, dict) and result.get("status") == "success":
                successes.append(tick)
            else:
                failures.append({"ticker": tick, "reason": result.get("message") if isinstance(result, dict) else "Unknown error"})
                
        except Exception as e:
            print(f"[Error] Failed to train {tick}: {e}")
            failures.append({"ticker": tick, "reason": str(e)})
        finally:
            gc.collect()
            delay = random.uniform(1, 3)
            print(f"Sleeping for {delay:.2f}s before next ticker...\n")
            time.sleep(delay)
            
    print(f"===========================================================")
    print(f"BULK TRAINING BATCH SUMMARY")
    print(f"===========================================================")
    print(f"Total Processed: {len(tickers)}")
    print(f"Successful:      {len(successes)}")
    print(f"Failed:          {len(failures)}")
    
    if failures:
        print(f"\nFailed Tickers Details:")
        for f in failures:
            print(f" - {f['ticker']}: {f['reason']}")
            
    print(f"===========================================================")

if __name__ == "__main__":
    train_all_stocks()
