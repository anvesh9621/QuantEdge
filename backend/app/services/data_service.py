import pandas as pd
import yfinance as yf
import time
from datetime import datetime, timedelta
from app.database.db import engine
from sqlalchemy import text
from app.ml.features import calculate_features
from curl_cffi import requests as cffi_requests

# Create a browser-impersonating session to bypass basic bot protection
try:
    yf_session = cffi_requests.Session(impersonate="chrome110")
except Exception as e:
    print(f"Failed to initialize curl_cffi session: {e}. Falling back to default.")
    yf_session = None

def _execute_with_retry(func, ticker_symbol, *args, **kwargs):
    """
    Executes a function (like yf.download) with exponential backoff retries.
    Waits 10s, 30s, 90s on failure before giving up.
    """
    max_retries = 3
    delays = [10, 30, 90]
    
    for attempt in range(max_retries + 1):
        if attempt > 0:
            print(f"[{ticker_symbol}] Attempt {attempt}/{max_retries}...")
            
        try:
            result = func(*args, **kwargs)
            
            # yfinance often returns empty DataFrames on rate limits instead of raising exceptions
            if isinstance(result, pd.DataFrame) and result.empty:
                raise ValueError("Received empty DataFrame, possible rate limit.")
                
            if attempt > 0:
                print(f"[{ticker_symbol}] Succeeded on attempt {attempt}")
                
            return result
        except Exception as e:
            if attempt < max_retries:
                wait_time = delays[attempt]
                print(f"[{ticker_symbol}] Rate limited on attempt {attempt}, waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                print(f"[{ticker_symbol}] FAILED after {max_retries} attempts — giving up")
                raise e

def get_or_update_stock_data(ticker_symbol: str, skip_update: bool = False) -> pd.DataFrame:
    """
    Fetches raw stock data from DB for ticker. 
    If data is stale (missing days up to today) and skip_update is False, it backfills using yfinance with retries.
    """
    query = text("SELECT date, open, high, low, close, volume FROM stock_data WHERE ticker = :ticker ORDER BY date ASC")
    df = pd.read_sql(query, engine, params={"ticker": ticker_symbol})
    
    if not df.empty:
        df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)
    
    yf_ticker = f"{ticker_symbol}.NS"
    today = datetime.today()
    new_data = pd.DataFrame()
    
    if not skip_update:
        if df.empty:
            start_date = (today - timedelta(days=1825)).strftime('%Y-%m-%d')
            print(f"[{ticker_symbol}] No DB history. Fetching from {start_date}...")
            try:
                new_data = _execute_with_retry(yf.download, ticker_symbol, yf_ticker, start=start_date, progress=False, session=yf_session, threads=False)
            except Exception:
                print(f"[{ticker_symbol}] Giving up on full history fetch.")
        else:
            max_date = df['date'].max()
            if (today - max_date).days >= 1:
                start_date = (max_date + timedelta(days=1)).strftime('%Y-%m-%d')
                end_date = (today + timedelta(days=1)).strftime('%Y-%m-%d')
                print(f"[{ticker_symbol}] Stale DB history. Fetching delta from {start_date} to {end_date}...")
                try:
                    new_data = _execute_with_retry(yf.download, ticker_symbol, yf_ticker, start=start_date, end=end_date, progress=False, session=yf_session, threads=False)
                except Exception:
                    print(f"[{ticker_symbol}] Giving up on incremental fetch.")
            
    if not new_data.empty:
        new_data = new_data.reset_index()
        if isinstance(new_data.columns, pd.MultiIndex):
            new_data.columns = new_data.columns.get_level_values(0)
            
        rename_map = {
            'Date': 'date', 'Open': 'open', 'High': 'high', 
            'Low': 'low', 'Close': 'close', 'Volume': 'volume'
        }
        
        cols = [c for c in new_data.columns if c in rename_map.keys()]
        new_data = new_data[cols].rename(columns=rename_map)
        
        new_data['ticker'] = ticker_symbol
        new_data['date'] = pd.to_datetime(new_data['date']).dt.tz_localize(None)
        
        try:
            new_data.to_sql('stock_data', engine, if_exists='append', index=False)
            df = pd.concat([df, new_data], ignore_index=True)
            print(f"[{ticker_symbol}] Successfully appended {len(new_data)} new rows to DB.")
        except Exception as e:
            print(f"[{ticker_symbol}] Failed to append to DB: {e}")
            
    if not df.empty:
        df = df.drop_duplicates(subset=['date']).sort_values(by='date').reset_index(drop=True)
        
    return df

def get_processed_stock_data(ticker_symbol: str, for_training=True, skip_update=False) -> pd.DataFrame:
    df = get_or_update_stock_data(ticker_symbol, skip_update=skip_update)
    if df.empty:
        raise ValueError(f"No data available for ticker {ticker_symbol}")
    return calculate_features(df, for_training=for_training)

_fundamentals_cache = {}

def get_stock_fundamentals(ticker_symbol: str) -> dict:
    try:
        current_time = time.time()
        # Check cache (300 seconds TTL)
        if ticker_symbol in _fundamentals_cache:
            timestamp, data = _fundamentals_cache[ticker_symbol]
            if current_time - timestamp < 300:
                print(f"[{ticker_symbol}] Returning fundamentals from cache.")
                return data
                
        yf_ticker = f"{ticker_symbol}.NS"
        
        # Helper to fetch info using the custom session
        def _fetch_info():
            stock = yf.Ticker(yf_ticker, session=yf_session)
            info = stock.info
            if not info:
                raise ValueError("Empty info dict returned.")
            return info
            
        info = _execute_with_retry(_fetch_info, ticker_symbol)
        
        result = {
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
        
        # Store in cache
        _fundamentals_cache[ticker_symbol] = (current_time, result)
        return result
        
    except Exception as e:
        print(f"Error fetching fundamentals for {ticker_symbol}: {e}")
        return {}
