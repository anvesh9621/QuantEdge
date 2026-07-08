import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.database.db import engine, Base, SessionLocal
from app.database.models import StockData
from app.routes.api import router as api_router
from app.ws_manager import manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create tables
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────
    # Pre-load all tickers from the DB so the upstream WS subscribes to them
    # immediately, even before any browser client connects.
    try:
        db = SessionLocal()
        rows = db.query(StockData.ticker).distinct().all()
        tickers = [r[0] for r in rows]
        db.close()
        manager.set_all_tickers(tickers)
        logger.info(f"Loaded {len(tickers)} tickers from DB for WS subscription.")
    except Exception as e:
        logger.error(f"Failed to pre-load tickers at startup: {e}")

    manager.start()
    yield

    # ── Shutdown (Task 4) ─────────────────────────────────────────────────
    # Sends clean close frames to every browser client and closes Yahoo upstream.
    await manager.shutdown()


app = FastAPI(
    title="Stock Market Prediction API",
    description="Backend for Stock Market Prediction and Decision Support System",
    version="1.0.0",
    lifespan=lifespan,
)

# Setup CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.websocket("/ws/prices/{ticker}")
async def websocket_prices(websocket: WebSocket, ticker: str):
    await manager.connect(websocket, ticker)
    try:
        while True:
            # We push data TO the client; just keep the receive loop alive.
            await websocket.receive_text()
    except WebSocketDisconnect:
        # Clean disconnect (browser tab closed normally)
        await manager.disconnect(websocket, ticker)
    except Exception:
        # Abrupt drop (network loss, process kill, etc.) — Task 1 guarantee:
        # cleanup still happens so the client is removed from broadcast list.
        await manager.disconnect(websocket, ticker)


@app.get("/")
def health_check():
    return {"status": "ok", "message": "Stock Market Prediction API is running"}
