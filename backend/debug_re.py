import pandas as pd
from app.database.db import engine
from sqlalchemy import text

ticker_symbol = 'RELIANCE'
query = text("SELECT date, open, high, low, close, volume FROM stock_data WHERE ticker = :ticker ORDER BY date ASC")
df = pd.read_sql(query, engine, params={"ticker": ticker_symbol})

print(f"DB length: {len(df)}")
from app.ml.features import calculate_features

if len(df) > 0:
    df = calculate_features(df, for_training=True)
    print(f"After feats: {len(df)}")
