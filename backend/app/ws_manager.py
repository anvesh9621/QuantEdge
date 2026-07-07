import asyncio
import json
import base64
import logging
from typing import Dict, Set
from fastapi import WebSocket
import websockets
from websockets.exceptions import ConnectionClosed

# Import the compiled protobuf
from app.schemas import pricing_pb2

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Maps ticker (e.g. "RELIANCE") to a set of active FastAPI WebSockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Stores the latest decoded JSON tick per ticker
        self.last_ticks: Dict[str, dict] = {}
        
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

    async def connect(self, websocket: WebSocket, ticker: str):
        """Called when a client connects to our FastAPI backend for a specific ticker."""
        await websocket.accept()
        if ticker not in self.active_connections:
            self.active_connections[ticker] = set()
            # If this is a new ticker, we need to subscribe the upstream to it
            await self._subscribe_upstream([ticker])
            
        self.active_connections[ticker].add(websocket)
        logger.info(f"Client connected to {ticker}. Total: {len(self.active_connections[ticker])}")

        # Instantly push the last known cached tick so the client isn't waiting
        if ticker in self.last_ticks:
            try:
                # Add a flag to indicate it's a cached/initial payload
                payload = dict(self.last_ticks[ticker])
                payload["is_stale"] = False
                await websocket.send_json(payload)
            except Exception as e:
                logger.error(f"Error sending initial cache to client: {e}")

    def disconnect(self, websocket: WebSocket, ticker: str):
        """Called when a client disconnects."""
        if ticker in self.active_connections:
            self.active_connections[ticker].discard(websocket)
            logger.info(f"Client disconnected from {ticker}. Remaining: {len(self.active_connections[ticker])}")
            if not self.active_connections[ticker]:
                del self.active_connections[ticker]
                # We could potentially unsubscribe from upstream here to save bandwidth, 
                # but leaving it running is fine for a small set of tickers.

    async def _subscribe_upstream(self, tickers: list):
        """Sends a subscribe message to the active upstream Yahoo connection."""
        if self._upstream_ws and self._upstream_ws.open:
            # Yahoo expects tickers with .NS for Indian stocks
            yf_tickers = [f"{t}.NS" for t in tickers]
            try:
                msg = json.dumps({"subscribe": yf_tickers})
                await self._upstream_ws.send(msg)
                logger.info(f"Subscribed upstream to: {yf_tickers}")
            except Exception as e:
                logger.error(f"Failed to subscribe upstream: {e}")

    async def _broadcast(self, ticker: str, data: dict):
        """Forks the decoded JSON tick to all connected FastAPI clients for this ticker."""
        if ticker in self.active_connections:
            disconnected = set()
            for ws in self.active_connections[ticker]:
                try:
                    await ws.send_json(data)
                except Exception:
                    # Client probably dropped ungracefully
                    disconnected.add(ws)
            
            # Cleanup dead connections
            for ws in disconnected:
                self.disconnect(ws, ticker)

    def _protobuf_to_dict(self, msg) -> dict:
        """Helper to convert the decoded Protobuf object to a standard Python dict."""
        return {
            "id": msg.id,
            "price": msg.price,
            "time": msg.time,
            "change": getattr(msg, "change", None),
            "changePercent": getattr(msg, "changePercent", None),
            "dayVolume": getattr(msg, "dayVolume", None),
            "dayHigh": getattr(msg, "dayHigh", None),
            "dayLow": getattr(msg, "dayLow", None),
            "marketcap": getattr(msg, "marketcap", None)
        }

    async def _upstream_loop(self):
        """The persistent background task that manages the Yahoo Finance connection."""
        uri = "wss://streamer.finance.yahoo.com"
        
        while self._is_running:
            if self.consecutive_failures >= self.max_failures:
                logger.warning(f"Circuit breaker triggered! Too many upstream failures. Cooling down for {self.cooldown_period}s.")
                await asyncio.sleep(self.cooldown_period)
                self.consecutive_failures = 0 # reset after cooldown
                
            try:
                logger.info("Connecting to Yahoo Finance upstream...")
                async with websockets.connect(uri, ping_interval=30, ping_timeout=10) as ws:
                    self._upstream_ws = ws
                    self.consecutive_failures = 0 # Success! Reset failure count.
                    logger.info("Successfully connected to Yahoo upstream.")
                    
                    # Sub to any tickers clients are currently waiting for
                    if self.active_connections:
                        await self._subscribe_upstream(list(self.active_connections.keys()))
                        
                    # Receive loop
                    async for message in ws:
                        try:
                            # Yahoo sends base64 encoded strings over WS
                            decoded_bytes = base64.b64decode(message)
                            pricing_data = pricing_pb2.PricingData()
                            pricing_data.ParseFromString(decoded_bytes)
                            
                            # Yahoo ID looks like "RELIANCE.NS". We strip ".NS" to match our internal ticker
                            raw_id = pricing_data.id
                            ticker = raw_id.replace(".NS", "")
                            
                            data_dict = self._protobuf_to_dict(pricing_data)
                            data_dict["is_stale"] = False
                            
                            # Cache the latest tick
                            self.last_ticks[ticker] = data_dict
                            
                            # Broadcast to all clients watching this ticker
                            await self._broadcast(ticker, data_dict)
                            
                        except Exception as e:
                            logger.error(f"Error decoding upstream message: {e}")
                            
            except Exception as e:
                self.consecutive_failures += 1
                delay = min(self.base_delay * (2 ** (self.consecutive_failures - 1)), self.max_delay)
                logger.error(f"Upstream connection failed ({e}). Retrying in {delay}s... (Failure {self.consecutive_failures}/{self.max_failures})")
                
                # While we're disconnected, optionally broadcast a "stale" ping to clients if they've been waiting too long
                # Here we just rely on the frontend detecting connection drops or delayed data via timestamps.
                
                await asyncio.sleep(delay)
            finally:
                self._upstream_ws = None

    def start(self):
        """Starts the upstream connection loop in the background."""
        if not self._is_running:
            self._is_running = True
            self._bg_task = asyncio.create_task(self._upstream_loop())
            logger.info("WebSocket Manager started.")

    def stop(self):
        """Stops the upstream connection loop."""
        self._is_running = False
        if self._bg_task:
            self._bg_task.cancel()
        logger.info("WebSocket Manager stopped.")

# Singleton instance
manager = ConnectionManager()
