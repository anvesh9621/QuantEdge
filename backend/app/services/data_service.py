import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from app.database.db import engine
from sqlalchemy import text
from app.ml.features import calculate_features

def get_or_update_stock_data(ticker_symbol: str, skip_update: bool = False) -> pd.DataFrame:
    """
    Fetches raw stock data from DB for ticker. 
    If data is stale (missing days up to today) and skip_update is False, it backfills using yfinance.
    """
    query = text("SELECT date, open, high, low, close, volume FROM stock_data WHERE ticker = :ticker ORDER BY date ASC")
    df = pd.read_sql(query, engine, params={"ticker": ticker_symbol})
    
    if not df.empty:
        df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)
    
    # yfinance uses .NS suffix for NSE Nifty 50 stocks (e.g. RELIANCE.NS)
    yf_ticker = f"{ticker_symbol}.NS"
    
    today = datetime.today()
    
    new_data = pd.DataFrame()
    if not skip_update:
        if df.empty:
            # If absolutely no history, fetch last 5 years
            start_date = (today - timedelta(days=1825)).strftime('%Y-%m-%d')
            new_data = yf.download(yf_ticker, start=start_date, progress=False)
        else:
            max_date = df['date'].max()
            # If the gap is more than 1 day (ignoring weekends) we try to fetch missing
            if (today - max_date).days >= 1:
                # We fetch starting from max_date + 1 day
                start_date = (max_date + timedelta(days=1)).strftime('%Y-%m-%d')
                end_date = (today + timedelta(days=1)).strftime('%Y-%m-%d')
                new_data = yf.download(yf_ticker, start=start_date, end=end_date, progress=False)
            
    if not new_data.empty:
        new_data = new_data.reset_index()
        # Yfinance sometimes returns MultiIndex columns, we flatten them
        if isinstance(new_data.columns, pd.MultiIndex):
            new_data.columns = new_data.columns.get_level_values(0)
            
        rename_map = {
            'Date': 'date', 'Open': 'open', 'High': 'high', 
            'Low': 'low', 'Close': 'close', 'Volume': 'volume'
        }
        
        cols = [c for c in new_data.columns if c in rename_map.keys()]
        new_data = new_data[cols].rename(columns=rename_map)
        
        # Ensure correct types and clean up
        new_data['ticker'] = ticker_symbol
        new_data['date'] = pd.to_datetime(new_data['date']).dt.tz_localize(None)
        
        # Append to the database
        try:
            new_data.to_sql('stock_data', engine, if_exists='append', index=False)
            df = pd.concat([df, new_data], ignore_index=True)
        except Exception as e:
            print(f"Failed to append missing yfinance data to DB for {ticker_symbol}: {e}")
            
    if not df.empty:
        df = df.drop_duplicates(subset=['date']).sort_values(by='date').reset_index(drop=True)
        
    return df

def get_processed_stock_data(ticker_symbol: str, for_training=True, skip_update=False) -> pd.DataFrame:
    """
    Returns a clean DataFrame full of indicators ready for ML training or prediction.
    """
    df = get_or_update_stock_data(ticker_symbol, skip_update=skip_update)
    if df.empty:
        raise ValueError(f"No data available for ticker {ticker_symbol}")
    
    return calculate_features(df, for_training=for_training)

def get_stock_fundamentals(ticker_symbol: str) -> dict:
    """
    Fetches real-time fundamental info from yfinance to display in the UI.
    """
    try:
        yf_ticker = f"{ticker_symbol}.NS"
        stock = yf.Ticker(yf_ticker)
        info = stock.info
        
        return {
            "market_cap": info.get("marketCap", 0),
            "pe_ratio": info.get("trailingPE", 0),
            "dividend_yield": info.get("dividendYield", 0),
            "volume_today": info.get("volume", 0),
            "volume_avg": info.get("averageVolume", 0),
            "fifty_day_avg": info.get("fiftyDayAverage", 0),
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown"),
            "current_price": info.get("currentPrice", 0),
            "previous_close": info.get("previousClose", 0),
        }
    except Exception as e:
        print(f"Error fetching fundamentals for {ticker_symbol}: {e}")
        return {}
