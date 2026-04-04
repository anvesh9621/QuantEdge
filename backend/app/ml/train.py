import os
import joblib
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, mean_absolute_error, mean_squared_error
from app.services.data_service import get_processed_stock_data

MODELS_DIR = "models"
os.makedirs(MODELS_DIR, exist_ok=True)

FEATURES = ['SMA_20', 'RSI_14', 'daily_return', 'volatility_20']

def train_model(ticker_symbol: str, model_type='rf'):
    """
    Trains TWO machine learning models for a specific ticker and saves them:
    1. A Classifier for predicting direction (UP/DOWN signal strength)
    2. A Regressor for predicting exact next-day price
    """
    print(f"[{ticker_symbol}] Fetching data and calculating features...")
    df = get_processed_stock_data(ticker_symbol, for_training=True)
    
    if df.empty or len(df) < 50:
        print(f"[{ticker_symbol}] Not enough data to train.")
        return False
        
    X = df[FEATURES]
    # Classifier target (Binary: 1=UP, 0=DOWN)
    y_class = df['target']
    # Regressor target (Exact next day close price)
    y_reg = df['target_price']
    
    # Chronological Split (No random shuffling, to preserve time series integrity)
    split_idx = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    
    y_class_train, y_class_test = y_class.iloc[:split_idx], y_class.iloc[split_idx:]
    y_reg_train, y_reg_test = y_reg.iloc[:split_idx], y_reg.iloc[split_idx:]
    
    print(f"[{ticker_symbol}] Training on {len(X_train)} samples, testing on {len(X_test)}...")
    
    # ── 1. Train Classifier ──────────────────────────────────────────────────
    # Reduced depth from 10->6 to keep classifier size under 500KB
    classifier = RandomForestClassifier(n_estimators=50, max_depth=6, random_state=42)
    classifier.fit(X_train, y_class_train)
    
    class_pred = classifier.predict(X_test)
    acc = accuracy_score(y_class_test, class_pred)
    print(f"[{ticker_symbol}] Classification Accuracy (Direction): {acc*100:.2f}%")
    
    class_model_path = os.path.join(MODELS_DIR, f"{ticker_symbol}_{model_type}.pkl")
    if os.path.exists(class_model_path): os.remove(class_model_path) # Auto-delete old huge models
    joblib.dump(classifier, class_model_path, compress=3) # Add compression!
    
    # ── 2. Train Regressor ───────────────────────────────────────────────────
    # Drastically reduced depth from 15->5 and estimators to fix 40MB file sizes.
    regressor = RandomForestRegressor(n_estimators=30, max_depth=5, random_state=42)
    regressor.fit(X_train, y_reg_train)
    
    reg_pred = regressor.predict(X_test)
    mae = mean_absolute_error(y_reg_test, reg_pred)
    print(f"[{ticker_symbol}] Regression MAE: ₹{mae:.2f}")
    
    reg_model_path = os.path.join(MODELS_DIR, f"{ticker_symbol}_{model_type}_reg.pkl")
    if os.path.exists(reg_model_path): os.remove(reg_model_path) # Auto-delete old huge models
    joblib.dump(regressor, reg_model_path, compress=3) # Add compression!
    
    print(f"[{ticker_symbol}] Models saved successfully.\n")
    return True

if __name__ == "__main__":
    train_model('RELIANCE', 'rf')
