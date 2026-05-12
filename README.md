<div align="center">

# ⚡ QuantEdge

### AI-Powered Stock Market Decision Support System

**Real-time market intelligence for NIFTY 50 | Built with FastAPI + React**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgAdmin-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.pgadmin.org/)
[![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-ML-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white)](https://scikit-learn.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

</div>

---

## 📖 Overview

**QuantEdge** is a full-stack, fintech-grade stock market decision support system purpose-built for the Indian NIFTY 50 market. It combines a **Dual-Model Machine Learning pipeline** with live market data to generate institutional-quality BUY / SELL / HOLD signals for 50 major Indian equities.

The system uses two independent AI models working in tandem — a **Random Forest Classifier** for directional probability and a **Random Forest Regressor** for precise next-day price targeting — then applies a proprietary multi-factor scoring engine to synthesize a single, confident trading decision.

> ⚠️ **Disclaimer:** QuantEdge is an educational analytical framework and is not intended as financial or investment advice. Always do your own research before making investment decisions.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🤖 **Dual AI Engine** | Classifier (direction) + Regressor (price target) working in parallel |
| 📊 **TradingView Charts** | Professional candlestick & area charts via Lightweight Charts v4 |
| 📡 **Live Market Data** | Real-time fundamentals streamed directly from Yahoo Finance API |
| 🧮 **Multi-Signal Scoring** | RSI, SMA, volatility, and classifier confidence fused into one decision |
| 📈 **52-Week Analytics** | High/Low, % from peak, % from trough |
| 💬 **Explainable AI** | Every signal comes with a human-readable reasoning breakdown |
| 🌡️ **Market Sentiment** | Custom gauge from Extreme Fear → Extreme Greed |
| 🔄 **Auto-Training** | Background model training triggers automatically on first request |
| 💾 **PostgreSQL Persistence** | 235,000+ rows of historical NIFTY 50 data stored in a local pgAdmin PostgreSQL database |
| 🎨 **Dark HUD Interface** | Deep-space themed professional UI with real-time animated indicators |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        QuantEdge System                         │
│                                                                  │
│  ┌──────────────────┐         ┌──────────────────────────────┐  │
│  │   React Frontend │ ──API── │      FastAPI Backend          │  │
│  │   (Vite + JSX)   │         │                              │  │
│  └──────────────────┘         │  ┌──────────┐ ┌───────────┐ │  │
│                                │  │ ML Models│ │ Data Svc  │ │  │
│  Chart Library:                │  │ ┌──────┐ │ │ yfinance  │ │  │
│  lightweight-charts v4         │  │ │  RF  │ │ │ SQLAlchemy│ │  │
│                                │  │ │Class │ │ └───────────┘ │  │
│  Key Components:               │  │ ├──────┤ │               │  │
│  • AdvancedChart               │  │ │  RF  │ │ ┌───────────┐ │  │
│  • Dashboard                   │  │ │ Reg  │ │ │ PostgreSQL│ │  │
│  • Sidebar (50 tickers)        │  │ └──────┘ │ │ (pgAdmin) │ │  │
│                                │  └──────────┘ └───────────┘ │  │
│                                └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

### Backend
| Technology | Purpose |
|---|---|
| **FastAPI** | High-performance async REST API with auto-generated docs |
| **Scikit-Learn** | Random Forest Classifier + Regressor for ML predictions |
| **Pandas + Pandas-TA** | Data processing, RSI, SMA, and volatility indicator calculation |
| **yfinance** | Live market fundamentals and historical price ingestion |
| **SQLAlchemy** | ORM for PostgreSQL database interaction |
| **Joblib** | Compressed model serialization for fast disk I/O |

### Frontend
| Technology | Purpose |
|---|---|
| **React 18 + Vite** | Lightning-fast component-based UI framework |
| **TradingView Lightweight Charts** | Professional HTML5 canvas chart rendering |
| **Vanilla CSS** | Custom dark design system with CSS variables |
| **Inter + JetBrains Mono** | Premium typography from Google Fonts |

### Database & Infrastructure
| Technology | Purpose |
|---|---|
| **PostgreSQL (pgAdmin)** | Local PostgreSQL database with 235k+ stock records |
| **Python-dotenv** | Environment variable management |

---

## 🤖 ML Pipeline Deep Dive

### 1. Feature Engineering (`features.py`)
The raw OHLCV data is transformed into 4 predictive technical features:

| Feature | Indicator | Window |
|---|---|---|
| `SMA_20` | Simple Moving Average | 20 days |
| `RSI_14` | Relative Strength Index | 14 days |
| `daily_return` | % price change | 1 day |
| `volatility_20` | Rolling std of returns | 20 days |

### 2. Dual Model Training (`train.py`)
- **80/20 chronological split** (no lookahead bias)
- `RandomForestClassifier` → predicts direction (up/down)
- `RandomForestRegressor` → predicts next-day close price
- Models are compressed and saved as `.pkl` files per ticker

### 3. Multi-Signal Decision Engine (`predict.py`)
Signals are scored on a weighted scale to produce a final decision:

```
Score = Regressor signal (+/-1.0) 
      + Classifier signal (up to +/-1.25)  
      + RSI override (+/-0.8)
      + Volatility dampener (x0.5 multiplier)

Score >= +0.8 → BUY  🟢
Score <= -0.8 → SELL  🔴
Otherwise    → HOLD  🟡
```

---

## 💻 Local Setup

### Prerequisites
- Python 3.12+
- Node.js 18+
- PostgreSQL database — install [pgAdmin](https://www.pgadmin.org/) and create a local database

### 1. Clone the Repository
```bash
git clone https://github.com/anvesh9621/QuantEdge.git
cd QuantEdge
```

### 2. Configure the Backend
```bash
cd backend

# Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\activate      # Windows
# source venv/bin/activate   # macOS / Linux

# Install dependencies
pip install -r requirements.txt
```

Create a `.env` file in the `backend/` directory:
```env
DATABASE_URL=postgresql://your_user:your_password@localhost/your_db
```

### 3. Seed the Database
```bash
# Import historical NIFTY 50 data from the CSV files in /historical_data
python import_data.py
```

### 4. Train ML Models
```bash
# Train models for all 50 stocks at once (takes ~5-10 minutes)
python train_all.py
```

### 5. Start the Backend API
```bash
uvicorn app.main:app --reload
# API live at: http://localhost:8000
# Docs live at: http://localhost:8000/docs
```

### 6. Start the Frontend Dashboard
```bash
# Open a new terminal
cd frontend
npm install
npm run dev
# Dashboard live at: http://localhost:5173
```

---

## 📡 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/stocks` | List all 50 available NIFTY tickers |
| `GET` | `/api/history/{ticker}` | Last 1000 days of OHLCV data |
| `GET` | `/api/predict/{ticker}` | Full AI prediction payload |
| `GET` | `/api/fundamentals/{ticker}` | Live market fundamentals |
| `GET` | `/api/history/predictions/{ticker}` | Past prediction log |

Interactive API docs are auto-generated at `http://localhost:8000/docs`.

---

## 📁 Project Structure

```
QuantEdge/
├── backend/
│   ├── app/
│   │   ├── database/
│   │   │   ├── db.py           # SQLAlchemy engine & session
│   │   │   └── models.py       # ORM table definitions
│   │   ├── ml/
│   │   │   ├── features.py     # Technical indicator calculations
│   │   │   ├── predict.py      # Dual-model prediction engine
│   │   │   └── train.py        # Model training pipeline
│   │   ├── routes/
│   │   │   └── api.py          # All REST API endpoints
│   │   ├── services/
│   │   │   └── data_service.py # DB queries & yfinance integration
│   │   └── main.py             # FastAPI app entry point
│   ├── historical_data/        # Raw NIFTY 50 CSV files
│   ├── models/                 # Saved .pkl model files
│   ├── import_data.py          # One-time DB seeding script
│   ├── train_all.py            # Bulk model training script
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── components/
    │   │   └── Dashboard.jsx   # Main app component
    │   ├── App.jsx
    │   ├── index.css           # Global design system
    │   └── main.jsx
    └── package.json
```

---

## 📊 Supported Stocks (NIFTY 50)

The system supports all 50 stocks in the NIFTY 50 index, including:

`RELIANCE` · `TCS` · `INFY` · `HDFCBANK` · `ICICIBANK` · `HINDUNILVR` · `ITC` · `KOTAKBANK` · `LT` · `WIPRO` · and 40 more.

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m 'feat: add some feature'`
4. Push to the branch: `git push origin feature/my-feature`
5. Open a Pull Request

---

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---

<div align="center">

Built with ❤️ for the Indian stock market

**[GitHub](https://github.com/anvesh9621/QuantEdge)** · **[Report Bug](https://github.com/anvesh9621/QuantEdge/issues)** · **[Request Feature](https://github.com/anvesh9621/QuantEdge/issues)**

</div>
