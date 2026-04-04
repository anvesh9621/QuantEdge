import os
import pandas as pd
from app.database.db import engine, Base
import app.database.models as models
from dotenv import load_dotenv

load_dotenv()

# Ensure tables are created first
Base.metadata.create_all(bind=engine)

HISTORICAL_DATA_DIR = "historical_data"

def import_historical_data():
    if not os.path.exists(HISTORICAL_DATA_DIR):
        print(f"Error: Directory '{HISTORICAL_DATA_DIR}' not found!")
        return

    csv_files = [f for f in os.listdir(HISTORICAL_DATA_DIR) if f.endswith('.csv')]
    
    if not csv_files:
        print("No CSV files found in the directory.")
        return

    print(f"Found {len(csv_files)} CSV files. Starting import...")

    total_rows = 0

    for file in csv_files:
        filepath = os.path.join(HISTORICAL_DATA_DIR, file)
        ticker = file.replace(".csv", "")
        
        # Read CSV
        df = pd.read_csv(filepath)
        
        # Filter for only Equity ('EQ') series if the column exists, to remove duplicates
        if 'Series' in df.columns:
            df = df[df['Series'] == 'EQ']
            
        # Standardize columns to match our database model
        # NSE format usually has: Date, Symbol, Series, Prev Close, Open, High, Low, Last, Close, VWAP, Volume...
        # We only need: date, ticker, open, high, low, close, volume
        
        # Rename columns to lowercase matching our model
        rename_map = {
            'Date': 'date',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume' 
        }
        
        # Keep only the mapped columns and Symbol if needed.
        # Actually we should force standard naming to prevent issues
        cols_to_keep = []
        for col in df.columns:
            if col in rename_map:
                cols_to_keep.append(col)
                
        df = df[cols_to_keep].rename(columns=rename_map)
        
        # Ensure ticker column exists explicitly
        df['ticker'] = ticker
        
        # Convert date to datetime
        df['date'] = pd.to_datetime(df['date'])
        
        # Write to PostgreSQL directly using pandas (incredibly fast)
        # We append to the 'stock_data' table
        try:
            df.to_sql('stock_data', engine, if_exists='append', index=False)
            print(f"✅ Imported {len(df)} rows for {ticker}")
            total_rows += len(df)
        except Exception as e:
            print(f"❌ Error inserting {ticker}: {e}")

    print(f"\n🎉 Import Complete! Successfully inserted {total_rows} total rows into PostgreSQL.")

if __name__ == "__main__":
    import_historical_data()
