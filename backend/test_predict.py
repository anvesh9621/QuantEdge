import json
import logging
# Suppress noisy yfinance/NumPy logs for a clean test output
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

from app.ml.predict import make_prediction

# Test on 3 diverse sample stocks
test_stocks = ['RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'WIPRO', 'ITC']

results = []
for stock in test_stocks:
    print(f"Testing {stock}...")
    try:
        res = make_prediction(stock, 'rf')
        results.append({
            "stock": res.get("stock", stock),
            "decision": res.get("decision", "Error"),
            "confidence": res.get("confidence", 0),
            "score": res.get("score"),
            "reason": res.get("reason", [])
        })
    except Exception as e:
        print(f"Error for {stock}: {e}")

print("\n=== FINAL PREDICTION RESULTS ===")
for r in results:
    decision = r['decision']
        
    print(f"{r['stock']:<10} | {decision:<4} | Conf: {r['confidence']*100:>4.1f}% | Score: {r['score']}")
    for reason in r['reason']:
        print(f"    - {reason}")
    print("-" * 50)
