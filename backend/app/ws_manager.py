import asyncio
import json
import base64
import logging
from typing import Dict, Set, List, Optional
from fastapi import WebSocket
import websockets

# Import the compiled protobuf
from app.schemas import pricing_pb2

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # Maps ticker (e.g. "RELIANCE") to a set of active FastAPI WebSockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Stores the latest decoded JSON tick per ticker
        self.last_ticks: Dict[str, dict] = {}

        # All known tickers (pre-loaded at startup so we subscribe even before clients connect)
        self._all_tickers: List[str] = []

        # Upstream state
        self._upstream_ws = None
        self._bg_task = None
        self._is_running = False

        # Circuit breaker & Backoff state
        self.consecutive_failures = 0
        self.max_failures = 10
        self.cooldown_period = 60
        self.base_delay = 1.0
        self.max_delay = 30.0

    def set_all_tickers(self, tickers: List[str]):
        """Called at startup with the full list of tickers from DB."""
        self._all_tickers = tickers
        logger.info(f"WSManager: pre-loaded {len(tickers)} tickers: {tickers}")

    # ── Client connect/disconnect ───────────────────────────────────────────

    async def connect(self, websocket: WebSocket, ticker: str):
        """Called when a browser client connects to /ws/prices/{ticker}."""
        await websocket.accept()

        if ticker not in self.active_connections:
            self.active_connections[ticker] = set()

        self.active_connections[ticker].add(websocket)
        logger.info(f"Client connected → {ticker}. Total clients: {len(self.active_connections[ticker])}")

        # Instantly push the last known cached tick so the client isn't staring at nothing
        if ticker in self.last_ticks:
            try:
                payload = dict(self.last_ticks[ticker])
                payload["is_stale"] = False
                await websocket.send_json(payload)
            except Exception as e:
                logger.warning(f"Error sending cached tick to new client: {e}")

    def disconnect(self, websocket: WebSocket, ticker: str):
        """Called when a browser client disconnects."""
        if ticker in self.active_connections:
            self.active_connections[ticker].discard(websocket)
            logger.info(f"Client disconnected from {ticker}. Remaining: {len(self.active_connections[ticker])}")
            if not self.active_connections[ticker]:
                del self.active_connections[ticker]

    # ── Upstream subscription ───────────────────────────────────────────────

    async def _send_subscription(self, ws, tickers: List[str]):
        """Fire a subscribe message on the upstream Yahoo connection."""
        if not tickers:
            return
        yf_tickers = [f"{t}.NS" for t in tickers]
        msg = json.dumps({"subscribe": yf_tickers})
        try:
            await ws.send(msg)
            logger.info(f"Subscribed upstream to: {yf_tickers}")
        except Exception as e:
            logger.error(f"Failed to send subscription: {e}")

    # ── Broadcast to clients ────────────────────────────────────────────────

    async def _broadcast(self, ticker: str, data: dict):
        """Fan out a decoded tick to all clients subscribed to this ticker."""
        connections = self.active_connections.get(ticker)
        if not connections:
            return

        dead: Set[WebSocket] = set()
        for ws in list(connections):
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)

        for ws in dead:
            self.disconnect(ws, ticker)

    # ── Protobuf decode ─────────────────────────────────────────────────────

    def _decode_message(self, raw_message: bytes) -> Optional[dict]:
        """
        Yahoo sends base64-encoded protobuf binary over the WebSocket.
        Returns a clean dict or None on failure.
        """
        try:
            decoded_bytes = base64.b64decode(raw_message)
        except Exception:
            # Might be a plain-text heartbeat/ping — ignore
            return None

        try:
            pricing_data = pricing_pb2.PricingData()
            pricing_data.ParseFromString(decoded_bytes)
        except Exception as e:
            logger.debug(f"Protobuf parse error (ignoring): {e}")
            return None

        # price == 0.0 means this protobuf message didn't carry price data — skip it
        if pricing_data.price == 0.0 or not pricing_data.id:
            return None

        # Build a clean JSON-serialisable dict
        # Use or None so unset 0-values don't mislead the frontend
        result = {
            "id": pricing_data.id,
            "price": float(pricing_data.price),
            "time": int(pricing_data.time),
            "is_stale": False,
        }

        if pricing_data.change != 0.0:
            result["change"] = float(pricing_data.change)
        if pricing_data.changePercent != 0.0:
            result["changePercent"] = float(pricing_data.changePercent)
        if pricing_data.dayHigh != 0.0:
            result["dayHigh"] = float(pricing_data.dayHigh)
        if pricing_data.dayLow != 0.0:
            result["dayLow"] = float(pricing_data.dayLow)
        if pricing_data.dayVolume != 0:
            result["dayVolume"] = int(pricing_data.dayVolume)

        return result

    # ── Upstream loop ───────────────────────────────────────────────────────

    async def _upstream_loop(self):
        """
        Persistent background task:
        - Opens ONE connection to Yahoo Finance.
        - Subscribes to ALL known tickers.
        - Decodes ticks and broadcasts to clients.
        - Implements exponential backoff + circuit breaker on failure.
        """
        uri = "wss://streamer.finance.yahoo.com"

        while self._is_running:
            # ── Circuit breaker ───────────────────────────────────────────
            if self.consecutive_failures >= self.max_failures:
                logger.warning(
                    f"Circuit breaker open — too many failures. "
                    f"Cooling down for {self.cooldown_period}s."
                )
                await asyncio.sleep(self.cooldown_period)
                self.consecutive_failures = 0

            try:
                logger.info("Connecting to Yahoo Finance upstream WebSocket…")
                async with websockets.connect(
                    uri,
                    ping_interval=20,
                    ping_timeout=15,
                    close_timeout=10,
                ) as ws:
                    self._upstream_ws = ws
                    self.consecutive_failures = 0
                    logger.info("✓ Connected to Yahoo upstream.")

                    # Subscribe to ALL known tickers at once
                    tickers_to_sub = list(set(
                        self._all_tickers + list(self.active_connections.keys())
                    ))
                    await self._send_subscription(ws, tickers_to_sub)

                    # ── Receive loop ──────────────────────────────────────
                    async for raw_message in ws:
                        if not self._is_running:
                            break

                        data = self._decode_message(raw_message)
                        if data is None:
                            continue

                        raw_id: str = data["id"]
                        # Strip exchange suffixes so we match our DB tickers
                        ticker = raw_id.replace(".NS", "").replace(".BO", "")

                        # Update cache
                        self.last_ticks[ticker] = data

                        # Broadcast (fire-and-forget per client)
                        await self._broadcast(ticker, data)

            except websockets.ConnectionClosedOK:
                logger.info("Yahoo upstream closed cleanly. Reconnecting…")
            except websockets.ConnectionClosedError as e:
                self.consecutive_failures += 1
                delay = min(self.base_delay * (2 ** (self.consecutive_failures - 1)), self.max_delay)
                logger.error(
                    f"Yahoo upstream closed with error: {e}. "
                    f"Retrying in {delay}s… (failure {self.consecutive_failures}/{self.max_failures})"
                )
                await asyncio.sleep(delay)
            except Exception as e:
                self.consecutive_failures += 1
                delay = min(self.base_delay * (2 ** (self.consecutive_failures - 1)), self.max_delay)
                logger.error(
                    f"Upstream error: {e}. "
                    f"Retrying in {delay}s… (failure {self.consecutive_failures}/{self.max_failures})"
                )
                await asyncio.sleep(delay)
            finally:
                self._upstream_ws = None

    # ── Lifecycle ───────────────────────────────────────────────────────────

    def start(self):
        """Start the upstream connection background task."""
        if not self._is_running:
            self._is_running = True
            self._bg_task = asyncio.create_task(self._upstream_loop())
            logger.info("WebSocket Manager started.")

    def stop(self):
        """Stop the upstream connection background task."""
        self._is_running = False
        if self._bg_task:
            self._bg_task.cancel()
        logger.info("WebSocket Manager stopped.")


# Singleton instance imported by main.py and the WS route
manager = ConnectionManager()
