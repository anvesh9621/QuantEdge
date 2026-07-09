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
    yf_session = cffi_requests.Session(impersonate="chrome110", verify=False)
except Exception as e:
    print(f"Failed to initialize curl_cffi session: {e}. Falling back to default.")
    yf_session = None

def _execute_with_retry(func, ticker_symbol, *args, max_retries=3, **kwargs):
    """
    Executes a function (like yf.download) with exponential backoff retries.
    Waits 10s, 30s, 90s on failure before giving up.
    """
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
                if max_retries > 0:
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

def get_stock_fundamentals(ticker_symbol: str) -> dict:
    try:
        # Some NSE tickers were renamed/split; map to the correct current Yahoo Finance symbol
        YAHOO_TICKER_MAP = {
            "TATAMOTORS": "TMCV",   # Tata Motors restructured: now TMCV (Commercial Vehicles)
        }
        yf_ticker_base = YAHOO_TICKER_MAP.get(ticker_symbol.upper(), ticker_symbol)
        yf_ticker = f"{yf_ticker_base}.NS"
        stock = yf.Ticker(yf_ticker, session=yf_session)
        
        fundamentals = {
            "market_cap": 0, "volume_today": 0, "volume_avg": 0,
            "fifty_day_avg": 0, "current_price": 0, "previous_close": 0,
            "pe_ratio": 0, "dividend_yield": 0, "sector": "Unknown", "industry": "Unknown"
        }
        
        # 1. fast_info — lightweight, almost never rate-limited; gives price/volume metrics
        try:
            f_info = stock.fast_info
            fundamentals["market_cap"] = getattr(f_info, "market_cap", 0)
            fundamentals["volume_today"] = getattr(f_info, "last_volume", 0)
            fundamentals["volume_avg"] = getattr(f_info, "ten_day_average_volume", 0)
            fundamentals["fifty_day_avg"] = getattr(f_info, "fifty_day_average", 0)
            fundamentals["current_price"] = getattr(f_info, "last_price", 0)
            fundamentals["previous_close"] = getattr(f_info, "previous_close", 0)
        except Exception as e:
            print(f"fast_info failed for {ticker_symbol}: {e}")
            
        # 2. Screener.in — PRIMARY source for P/E and Dividend Yield
        #    Covers all NSE stocks, has no rate limits, is free and public.
        #    Some stocks have a different Screener slug than the NSE ticker.
        SCREENER_SLUG_MAP = {
            "TATAMOTORS": "TMCV",   # Tata Motors is listed as TMCV on Screener
            "MM":         "M-M",    # M&M: not in our 50 but future-proofed
        }
        screener_slug = SCREENER_SLUG_MAP.get(ticker_symbol.upper(), ticker_symbol.upper())
        
        try:
            from bs4 import BeautifulSoup
            screener_url = f"https://www.screener.in/company/{screener_slug}/consolidated/"
            sres = (yf_session.get(screener_url, timeout=7) if yf_session
                    else __import__('requests').get(screener_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=7, verify=False))
            
            if sres.status_code == 200:
                ssoup = BeautifulSoup(sres.content.decode('utf-8', errors='ignore'), 'html.parser')
                for li in ssoup.select('#top-ratios li'):
                    name_el = li.find('span', class_='name')
                    val_el  = li.find('span', class_='nowrap')
                    if not name_el or not val_el:
                        continue
                    name = name_el.text.strip()
                    # Strip currency symbols, whitespace, commas; keep digits and dot
                    raw = val_el.text.strip().replace(',', '')
                    numeric_str = ''.join(c for c in raw if c.isdigit() or c == '.').strip('.')
                    try:
                        numeric_val = float(numeric_str) if numeric_str else 0
                    except ValueError:
                        continue
                    if 'P/E' in name and fundamentals["pe_ratio"] == 0:
                        fundamentals["pe_ratio"] = numeric_val
                    elif 'Dividend Yield' in name and fundamentals["dividend_yield"] == 0:
                        fundamentals["dividend_yield"] = numeric_val
            else:
                print(f"Screener.in HTTP {sres.status_code} for {screener_slug}")
        except Exception as e:
            print(f"Screener.in scrape failed for {ticker_symbol}: {e}")

        # 3. Yahoo Finance HTML — fallback if Screener still didn't fill PE/Div
        if fundamentals["pe_ratio"] == 0 or fundamentals["dividend_yield"] == 0:
            try:
                from bs4 import BeautifulSoup
                yurl = f"https://finance.yahoo.com/quote/{yf_ticker}/"
                yres = (yf_session.get(yurl, timeout=5) if yf_session
                        else __import__('requests').get(yurl, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5, verify=False))
                    
                if yres.status_code == 200:
                    ysoup = BeautifulSoup(yres.text, 'html.parser')
                    if fundamentals["pe_ratio"] == 0:
                        for tag in ysoup.find_all('fin-streamer', {'data-field': 'trailingPE'}):
                            try:
                                val = float(tag.text.strip().replace(',', ''))
                                if val > 0:
                                    fundamentals["pe_ratio"] = val
                                    break
                            except Exception: pass
                    if fundamentals["dividend_yield"] == 0:
                        for li in ysoup.find_all('li'):
                            t = li.text.strip()
                            if 'Yield' in t and '%' in t:
                                try:
                                    fundamentals["dividend_yield"] = float(t.split('(')[1].split('%')[0])
                                    break
                                except Exception: pass
            except Exception as e:
                print(f"Yahoo HTML fallback failed for {ticker_symbol}: {e}")

        # 4. yfinance.info — last-resort for Sector/Industry labels (often rate-limited)
        try:
            info = stock.info
            if info:
                if not fundamentals["market_cap"]:
                    fundamentals["market_cap"] = info.get("marketCap", 0)
                if not fundamentals["pe_ratio"]:
                    fundamentals["pe_ratio"] = info.get("trailingPE", 0)
                if not fundamentals["dividend_yield"]:
                    fundamentals["dividend_yield"] = info.get("dividendYield", 0)
                fundamentals["sector"]   = info.get("sector", "Unknown")
                fundamentals["industry"] = info.get("industry", "Unknown")
        except Exception:
            pass  # Totally fine — sector/industry is cosmetic
            
        return fundamentals
    except Exception as e:
        print(f"Critical error fetching fundamentals for {ticker_symbol}: {e}")
        return {}
