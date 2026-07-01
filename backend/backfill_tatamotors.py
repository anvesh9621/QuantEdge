import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from app.database.db import SessionLocal
from app.database.models import StockData
import time

TICKER = "TATAMOTORS"
YF_TICKER = "TATAMOTORS.NS"
START = datetime(2021, 5, 1)
END = datetime.today()
CHUNK_MONTHS = 6

# Split into 6-month chunks
chunks = []
current = START
while current < END:
    next_chunk = min(current + timedelta(days=180), END)
    chunks.append((current, next_chunk))
    current = next_chunk

total_inserted = 0
for start, end in chunks:
    print(f"Fetching {YF_TICKER} from {start.date()} to {end.date()}...")
    try:
        df = yf.download(YF_TICKER, start=start, end=end, auto_adjust=True, progress=False)
        if df.empty:
            print(f"No data for this chunk, skipping.")
            time.sleep(3)
            continue
        
        with SessionLocal() as db:
            inserted = 0
            for date, row in df.iterrows():
                exists = db.query(StockData).filter(
                    StockData.ticker == TICKER,
                    StockData.date == date.date()
                ).first()
                if not exists:
                    db.add(StockData(
                        ticker=TICKER,
                        date=date.date(),
                        open=float(row['Open']),
                        high=float(row['High']),
                        low=float(row['Low']),
                        close=float(row['Close']),
                        volume=int(row['Volume'])
                    ))
                    inserted += 1
            db.commit()
            print(f"Inserted {inserted} rows for this chunk.")
            total_inserted += inserted
        
        time.sleep(2)  # be polite between chunks
    except Exception as e:
        print(f"Error on chunk {start.date()}-{end.date()}: {e}")
        time.sleep(5)
        continue

print(f"Done. Total rows inserted: {total_inserted}")
