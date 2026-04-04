import os
import joblib
import pandas as pd
from app.services.data_service import get_processed_stock_data

MODELS_DIR = "models"
FEATURES = ['SMA_20', 'RSI_14', 'daily_return', 'volatility_20']

def _classify_rsi(rsi: float) -> str:
    if rsi >= 70: return "OVERBOUGHT"
    elif rsi <= 30: return "OVERSOLD"
    elif rsi >= 60: return "BULLISH"
    elif rsi <= 40: return "BEARISH"
    else: return "NEUTRAL"

def _get_market_sentiment(rsi: float, close: float, sma: float) -> str:
    # A combined sentiment gauge from 0 (Extreme Fear) to 100 (Extreme Greed)
    sentiment_score = 50.0
    
    # RSI influence (-25 to +25)
    sentiment_score += (rsi - 50) / 2
    
    # Trend influence (-25 to +25)
    if close > sma:
        trend_pct = min(10.0, ((close - sma) / sma) * 100)
        sentiment_score += trend_pct * 2.5
    else:
        trend_pct = max(-10.0, ((close - sma) / sma) * 100)
        sentiment_score += trend_pct * 2.5
        
    sentiment_score = max(0, min(100, sentiment_score))
    
    if sentiment_score >= 80: return "EXTREME GREED"
    elif sentiment_score >= 60: return "GREED"
    elif sentiment_score <= 20: return "EXTREME FEAR"
    elif sentiment_score <= 40: return "FEAR"
    else: return "NEUTRAL"

def make_prediction(ticker_symbol: str, model_type='rf'):
    """
    Advanced prediction pipeline utilizing:
      1. Classifier model for directional probability
      2. Regressor model for exact next-day price targeting
    """
    class_model_path = os.path.join(MODELS_DIR, f"{ticker_symbol}_{model_type}.pkl")
    reg_model_path = os.path.join(MODELS_DIR, f"{ticker_symbol}_{model_type}_reg.pkl")

    if not os.path.exists(class_model_path) or not os.path.exists(reg_model_path):
        return {
            "error": f"Models for {ticker_symbol} not found. Please train first.",
            "decision": "HOLD",
            "current_price": 0,
        }

    classifier = joblib.load(class_model_path)
    regressor = joblib.load(reg_model_path)

    df = get_processed_stock_data(ticker_symbol, for_training=False)

    if df.empty:
        return {"error": "No data available", "decision": "HOLD"}

    latest_row = df.iloc[-1]
    X_pred = pd.DataFrame([latest_row[FEATURES]])

    # ── 1. Classifier Signal ──────────────────────────────────────────────────
    proba = classifier.predict_proba(X_pred)[0]
    proba_up   = float(proba[1])
    proba_down = float(proba[0])

    # ── 2. Regressor Price Target ─────────────────────────────────────────────
    predicted_price = float(regressor.predict(X_pred)[0])
    
    # ── 3. Mathematical Base ──────────────────────────────────────────────────
    rsi        = float(latest_row['RSI_14'])
    close      = float(latest_row['close'])
    sma        = float(latest_row['SMA_20'])
    volatility = float(latest_row['volatility_20'])
    daily_ret  = float(latest_row['daily_return']) * 100
    
    predicted_return_pct = ((predicted_price - close) / close) * 100

    # ── Risk level ───────────────────────────────────────────────────────────
    if volatility > 2.5: risk = "HIGH"
    elif volatility > 1.5: risk = "MEDIUM"
    else: risk = "LOW"

    # ── Multi-signal scoring for Decision ────────────────────────────────────
    score = 0.0
    signals = []

    # Regressor confidence mapping
    if predicted_return_pct > 1.0:
        score += 1.0
        signals.append(f"Regressor predicts strong +{predicted_return_pct:.2f}% gain (Target: ₹{predicted_price:.2f}).")
    elif predicted_return_pct < -1.0:
        score -= 1.0
        signals.append(f"Regressor predicts strong {predicted_return_pct:.2f}% loss (Target: ₹{predicted_price:.2f}).")
    else:
        signals.append(f"Regressor expects sideways movement to ₹{predicted_price:.2f} ({predicted_return_pct:+.2f}%).")

    # Classifier mapping
    if proba_up > 0.55:
        score += (proba_up - 0.50) * 5
        signals.append(f"Classifier confirms {proba_up*100:.1f}% probability of upward trend.")
    elif proba_down > 0.55:
        score -= (proba_down - 0.50) * 5
        signals.append(f"Classifier flags {proba_down*100:.1f}% probability of downward trend.")

    # RSI & SMA Overrides
    if rsi < 35:
        score += 0.8
        signals.append(f"RSI is oversold ({rsi:.1f}) — highlighting bounce potential.")
    elif rsi > 65:
        score -= 0.8
        signals.append(f"RSI is overbought ({rsi:.1f}) — risk of imminent pullback.")

    if volatility > 3.0 and score < 0:
        score *= 0.5
        signals.append("High volatility detected — dampening short-term sell signals.")

    # Final Decision Output
    BUY_THRESHOLD  =  0.8
    SELL_THRESHOLD = -0.8

    if score >= BUY_THRESHOLD:
        decision   = "BUY"
        confidence = min(0.99, 0.50 + score * 0.08)
    elif score <= SELL_THRESHOLD:
        decision   = "SELL"
        confidence = min(0.99, 0.50 + abs(score) * 0.08)
    else:
        decision   = "HOLD"
        confidence = max(0.40, 0.60 - abs(score) * 0.05)
        
    sentiment_label = _get_market_sentiment(rsi, close, sma)

    # ── 52-week data ─────────────────────────────────────────────────────────
    recent = df.tail(252)
    high_52w = float(recent['close'].max())
    low_52w  = float(recent['close'].min())
    pct_from_high = ((close - high_52w) / high_52w) * 100
    pct_from_low  = ((close - low_52w)  / low_52w)  * 100

    return {
        "stock": ticker_symbol,
        "decision": decision,
        "confidence": round(confidence, 4),
        "risk": risk,
        "current_price": round(close, 2),
        "predicted_price": round(predicted_price, 2),
        "predicted_return_pct": round(predicted_return_pct, 2),
        "signal_strength_up": round(proba_up, 4),
        "market_sentiment": sentiment_label,
        "reason": signals,
        "date": latest_row['date'].strftime('%Y-%m-%d'),
        "features": {
            "rsi": round(rsi, 2),
            "rsi_label": _classify_rsi(rsi),
            "sma": round(sma, 2),
            "volatility": round(volatility, 4),
        },
        "week52": {
            "high": round(high_52w, 2),
            "low": round(low_52w, 2),
            "pct_from_high": round(pct_from_high, 2),
            "pct_from_low": round(pct_from_low, 2),
        }
    }

if __name__ == "__main__":
    import json
    res = make_prediction('RELIANCE', 'rf')
    print(json.dumps(res, indent=2))
