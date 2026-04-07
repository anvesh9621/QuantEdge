# QuantEdge

**QuantEdge** is a FinTech-grade Stock Market Decision Support System. It utilizes a Dual-Model Machine Learning pipeline to provide algorithmic trading signals, predictive analytics, and real-time market data visualization for the NIFTY 50 Indian stock market.

## 🚀 Key Features

*   **Dual-Model Pipeline**: 
    *   **Regressor Engine**: Leverages `RandomForestRegressor` to mathematically predict exact next-day price targets.
    *   **Classifier Engine**: Calculates the historical directional probability of upward/downward trends.
*   **Algorithmic Signal Engine**: Evaluates conflicting model outputs mathematically to generate strict BUY/SELL/HOLD decision signals designed to protect capital.
*   **Real-Time Data Streaming**: Bypasses slow local database reads by scraping live real-time intraday fundamentals and pricing directly from the Yahoo Finance API.
*   **Institutional UI/UX**: Features a highly responsive, Deep-Space themed interface built in React, utilizing `lightweight-charts` by TradingView for immaculate gradient area charting.

## 🛠️ Technology Stack

**Backend**
*   **FastAPI**: High-performance asynchronous API framework.
*   **Scikit-Learn**: Core ML engines for algorithmic predictions.
*   **Pandas-TA & yfinance**: Data ingestion and technical indicator calculations (RSI, SMA, Volatility).
*   **SQLAlchemy**: Persistent storage for stock history and prediction caching.

**Frontend**
*   **React + Vite**: High-speed, instantaneous frontend tooling.
*   **TradingView Lightweight Charts**: Professional HTML5 canvas rendering for trading charts.
*   **Robust CSS Architecture**: Strictly controlled custom design system.

## 💻 Local Setup Installation

### 1. Clone the repository
```bash
git clone https://github.com/anvesh9621/QuantEdge.git
cd QuantEdge
```

### 2. Start the Backend API
Navigate to the backend directory, initialize the environment, and run the server:
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```
*The API will start on `http://localhost:8000`*

### 3. Start the Frontend Dashboard
Open a new terminal, navigate to the frontend directory, install Node dependencies, and start the Vite dev server:
```bash
cd frontend
npm install
npm run dev
```
*The Dashboard will launch instantly on `http://localhost:5173`*

## ⚖️ Disclaimer
QuantEdge is an analytical decision support framework built for educational analytical purposes. It should not be utilized as definitive financial advice.
