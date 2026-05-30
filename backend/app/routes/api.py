from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from datetime import datetime
import json
from app.database.db import get_db
from app.database.models import PredictionHistory, StockData
from app.ml.predict import make_prediction
from app.ml.train import train_model
from app.services.data_service import get_stock_fundamentals

router = APIRouter()

@router.get("/stocks")
def get_available_stocks(db: Session = Depends(get_db)):
    """Returns a list of unique tickers available in the database."""
    stocks = db.query(StockData.ticker).distinct().all()
    # Returns [('TCS',), ('RELIANCE',)] so we unpack it
    return {"stocks": [s[0] for s in stocks]}

@router.get("/history/{ticker}")
def get_stock_history(ticker: str, db: Session = Depends(get_db)):
    """Returns historical raw data for the TradingView chart (last 1000 days)."""
    data = db.query(StockData).filter(StockData.ticker == ticker).order_by(StockData.date.desc()).limit(1000).all()
    
    unique_data = {}
    for d in data:
        unique_data[d.date.strftime("%Y-%m-%d")] = d
        
    sorted_dates = sorted(unique_data.keys())
    return [{
        "time": date_str,
        "open": round(unique_data[date_str].open, 2),
        "high": round(unique_data[date_str].high, 2),
        "low": round(unique_data[date_str].low, 2),
        "close": round(unique_data[date_str].close, 2),
        "volume": unique_data[date_str].volume
    } for date_str in sorted_dates]

@router.get("/predict/{ticker}")
def predict_stock(ticker: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Generates a decision support prediction for a stock using the trained model."""
    try:
        res = make_prediction(ticker_symbol=ticker, model_type='rf')
        
        if "error" in res:
            # Model might not be trained. Trigger background training!
            background_tasks.add_task(train_model, ticker, 'rf')
            return res
            
        # Save to Prediction History
        history = PredictionHistory(
            ticker=ticker,
            prediction=res["decision"],
            confidence=res["confidence"],
            risk_level=res["risk"],
            reasoning=json.dumps(res["reason"]) # Store multiple reasons as JSON string
        )
        db.add(history)
        db.commit()
        
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/fundamentals/{ticker}")
def get_fundamentals(ticker: str):
    """Returns basic fundamental statistics from Yahoo Finance."""
    res = get_stock_fundamentals(ticker)
    if not res:
        raise HTTPException(status_code=404, detail="Fundamentals could not be fetched.")
    return res

@router.post("/train/{ticker}")
def background_train_model(ticker: str, background_tasks: BackgroundTasks):
    """Triggers model training in the background. Useful if model is missing."""
    background_tasks.add_task(train_model, ticker, 'rf')
    return {"message": f"Training process started in the background for {ticker}!"}

@router.get("/train_all")
def background_train_all_models(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Triggers bulk model training for ALL stocks in the background via a simple GET request."""
    tickers = db.query(StockData.ticker).distinct().all()
    tickers = [t[0] for t in tickers]
    
    def train_all_task():
        for t in tickers:
            try:
                train_model(t, 'rf')
            except Exception as e:
                print(f"Failed to train {t}: {e}")
                
    background_tasks.add_task(train_all_task)
    return {"message": f"Bulk training started in the background for {len(tickers)} stocks! This will take ~5-10 minutes. Check Render logs to see progress."}
