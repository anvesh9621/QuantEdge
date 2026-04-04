import pandas as pd
import pandas_ta as ta

def calculate_features(df: pd.DataFrame, for_training=True) -> pd.DataFrame:
    """
    Takes a DataFrame with columns: date, open, high, low, close, volume.
    Returns DataFrame with new technical indicator columns and a binary target.
    """
    # Ensure data is sorted chronologically
    df = df.sort_values(by='date').reset_index(drop=True)
    
    # Calculate 20-day Simple Moving Average (SMA)
    df['SMA_20'] = ta.sma(df['close'], length=20)
    
    # Calculate 14-day Relative Strength Index (RSI)
    df['RSI_14'] = ta.rsi(df['close'], length=14)
    
    # Daily Returns (Percentage change between today's and yesterday's close)
    df['daily_return'] = df['close'].pct_change()
    
    # Volatility (Rolling 20-day standard deviation of returns)
    df['volatility_20'] = df['daily_return'].rolling(window=20).std() * 100 # percentage scale
    
    # Target Variable 1 (Classification): 1 if next day's close is STRICTLY higher than today's close, else 0
    # Target Variable 2 (Regression): The actual exact value of next day's close price
    df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
    df['target_price'] = df['close'].shift(-1)
    
    if for_training:
        # In training, drop rows where any ML feature or target is NaN
        df = df.dropna(subset=['SMA_20', 'RSI_14', 'volatility_20', 'target_price', 'target'])
    else:
        # In prediction, drop NaN on features but keep the last row exactly!
        # The target column for the last row will still be 0 (from astype int conversion of False/NaN) but we don't use it anyway.
        df = df.dropna(subset=['SMA_20', 'RSI_14', 'volatility_20'])
        
    return df
