"""
ws_manager.py — Production-hardened WebSocket proxy & broadcast manager.

Architecture decisions:
- ONE upstream connection to Yahoo Finance shared across all browser clients.
- Per-ticker reference counting → subscribe/unsubscribe dynamically.
- Per-message exception isolation: decode errors never trigger reconnect.
- Broadcast iterates a snapshot copy so concurrent disconnects are safe.
- Graceful shutdown sends close frames to every connected browser client.
- Circuit breaker + exponential backoff protect the upstream reconnect loop.

Multi-instance note:
  last_ticks and active_connections are in-memory. Works perfectly on a
  single Render worker. For horizontal scaling, replace _broadcast() with
  a Redis Pub/Sub fan-out and store last_ticks in Redis too.
"""

import asyncio
import json
import base64
import logging
from typing import Dict, Set, List, Optional
from fastapi import WebSocket
import websockets
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

from app.schemas import pricing_pb2

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # ticker → set of currently connected browser WebSockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}

        # ticker → last decoded tick payload (serves as "instant cache" on connect)
        self.last_ticks: Dict[str, dict] = {}

        # Set of tickers the upstream Yahoo connection is currently subscribed to.
        # Used to avoid sending duplicate subscribe messages.
        self._subscribed_upstream: Set[str] = set()

        # Upstream Yahoo WebSocket (shared; one per process)
        self._upstream_ws = None
        self._bg_task: Optional[asyncio.Task] = None
        self._is_running = False

        # Circuit breaker / backoff
        self.consecutive_failures = 0
        self.max_failures = 10
        self.cooldown_period = 60       # seconds to wait after circuit breaker trips
        self.base_delay = 1.0           # first retry delay (seconds)
        self.max_delay = 30.0           # cap

    # ──────────────────────────────────────────────────────────────────────────
    # Public lifecycle helpers
    # ──────────────────────────────────────────────────────────────────────────

    def set_all_tickers(self, tickers: List[str]):
        """
        Called once at startup with all tickers from the DB.
        Ensures the upstream subscribes even before a browser client connects.
        (Task 1: pre-warm the subscription list.)
        """
        # We store them separately from active_connections so the upstream
        # can subscribe at connect time even when no browser is watching yet.
        # active_connections only grows when a browser actually connects.
        self._startup_tickers = list(tickers)
        logger.info(f"WSManager pre-loaded {len(tickers)} tickers: {tickers}")

    # ──────────────────────────────────────────────────────────────────────────
    # Task 1 — Dynamic per-ticker subscribe / unsubscribe
    # ──────────────────────────────────────────────────────────────────────────

    async def connect(self, websocket: WebSocket, ticker: str):
        """
        Called when a browser client opens /ws/prices/{ticker}.

        If this ticker has ZERO existing subscribers, send a Yahoo subscribe
        message BEFORE adding the client, so ticks are flowing by the time
        they arrive.  The client immediately receives the cached last tick
        so the UI is populated without waiting for the next real tick.
        """
        await websocket.accept()

        first_subscriber = ticker not in self.active_connections or \
                           len(self.active_connections[ticker]) == 0

        if ticker not in self.active_connections:
            self.active_connections[ticker] = set()

        if first_subscriber and ticker not in self._subscribed_upstream:
            # Subscribe upstream *before* adding the client to the broadcast list.
            await self._subscribe_ticker(ticker)

        self.active_connections[ticker].add(websocket)
        logger.info(
            f"Client connected → {ticker} "
            f"(total subscribers: {len(self.active_connections[ticker])})"
        )

        # Push cached tick immediately so the UI is never blank.
        if ticker in self.last_ticks:
            try:
                payload = dict(self.last_ticks[ticker])
                payload["is_stale"] = False
                await websocket.send_json(payload)
            except Exception as e:
                logger.warning(f"Could not push cached tick to new client: {e}")

    async def disconnect(self, websocket: WebSocket, ticker: str):
        """
        Called on clean disconnect (WebSocketDisconnect) AND on abrupt drops
        (the outer except in main.py's websocket_prices handler).

        When the last subscriber for a ticker leaves, we send an unsubscribe
        to Yahoo so we stop paying decode+bandwidth cost for that ticker.

        Task 1: reference counting via len(active_connections[ticker]).
        Task 4: async so we can await the unsubscribe send.
        """
        if ticker not in self.active_connections:
            return

        self.active_connections[ticker].discard(websocket)
        remaining = len(self.active_connections[ticker])
        logger.info(f"Client disconnected from {ticker}. Remaining: {remaining}")

        if remaining == 0:
            del self.active_connections[ticker]
            # Only unsubscribe if this ticker was not in the startup list.
            # We keep startup tickers subscribed so the cache stays warm.
            if ticker not in getattr(self, '_startup_tickers', []):
                await self._unsubscribe_ticker(ticker)
                self.last_ticks.pop(ticker, None)

    # ──────────────────────────────────────────────────────────────────────────
    # Task 1 — Upstream subscribe / unsubscribe helpers
    # ──────────────────────────────────────────────────────────────────────────

    async def _subscribe_ticker(self, ticker: str):
        """Send a Yahoo subscribe message for a single ticker."""
        yf_ticker = f"{ticker}.NS"
        if self._upstream_ws is not None:
            try:
                msg = json.dumps({"subscribe": [yf_ticker]})
                await self._upstream_ws.send(msg)
                self._subscribed_upstream.add(ticker)
                logger.info(f"↑ Subscribed upstream: {yf_ticker}")
            except Exception as e:
                logger.error(f"Failed to subscribe {yf_ticker}: {e}")
        else:
            # Upstream not connected yet; the loop will subscribe on reconnect.
            self._subscribed_upstream.discard(ticker)  # will re-subscribe on connect

    async def _unsubscribe_ticker(self, ticker: str):
        """Send a Yahoo unsubscribe message for a single ticker."""
        yf_ticker = f"{ticker}.NS"
        self._subscribed_upstream.discard(ticker)
        if self._upstream_ws is not None:
            try:
                msg = json.dumps({"unsubscribe": [yf_ticker]})
                await self._upstream_ws.send(msg)
                logger.info(f"↓ Unsubscribed upstream: {yf_ticker}")
            except Exception as e:
                logger.warning(f"Failed to unsubscribe {yf_ticker}: {e}")

    async def _subscribe_all_known(self, ws):
        """
        Called once right after the upstream connection is established.
        Subscribes to startup tickers + any already-active client tickers.
        Resets _subscribed_upstream so we get a clean state after reconnect.
        """
        self._subscribed_upstream.clear()
        all_tickers = list(set(
            getattr(self, '_startup_tickers', []) +
            list(self.active_connections.keys())
        ))
        if not all_tickers:
            return
        yf_tickers = [f"{t}.NS" for t in all_tickers]
        try:
            msg = json.dumps({"subscribe": yf_tickers})
            await ws.send(msg)
            self._subscribed_upstream.update(all_tickers)
            logger.info(f"Bulk-subscribed upstream to: {yf_tickers}")
        except Exception as e:
            logger.error(f"Failed bulk subscription: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # Task 3 — Safe concurrent broadcast
    # ──────────────────────────────────────────────────────────────────────────

    async def _broadcast(self, ticker: str, data: dict):
        """
        Fan out a decoded tick to all browser clients watching this ticker.

        Task 3 — safety guarantees:
        1. Snapshot the client set with list() BEFORE iterating — concurrent
           disconnects cannot mutate the set we're walking over.
        2. Each client's send is wrapped individually — one dead connection
           NEVER stops delivery to the rest.
        3. Dead clients are collected and cleaned up AFTER the iteration loop.
        """
        connections = self.active_connections.get(ticker)
        if not connections:
            return

        # ① Snapshot — never iterate the live set.
        snapshot: List[WebSocket] = list(connections)
        dead: List[WebSocket] = []

        for ws in snapshot:
            try:
                await ws.send_json(data)
            except Exception as exc:
                logger.debug(f"Dead client detected on {ticker}: {exc}")
                dead.add(ws) if hasattr(dead, 'add') else dead.append(ws)

        # ② Cleanup dead clients after the loop.
        for ws in dead:
            await self.disconnect(ws, ticker)

    # ──────────────────────────────────────────────────────────────────────────
    # Task 2 — Protobuf decode (per-message isolation)
    # ──────────────────────────────────────────────────────────────────────────

    def _decode_message(self, raw_message) -> Optional[dict]:
        """
        Decode a single Yahoo Finance WebSocket frame.

        Returns a clean dict on success, None on any decode failure.
        Errors here are LOGGED but never propagate — a bad frame must not
        trigger a reconnect or increment the circuit-breaker counter.

        Task 2: this is called inside its own per-message try/except in
        _upstream_loop so that decode failures are fully isolated.
        """
        # Step 1: base64 decode
        try:
            decoded_bytes = base64.b64decode(raw_message)
        except Exception:
            # Plain-text heartbeat or empty frame — ignore silently.
            return None

        # Step 2: protobuf parse
        try:
            pricing_data = pricing_pb2.PricingData()
            pricing_data.ParseFromString(decoded_bytes)
        except Exception as e:
            logger.debug(f"Protobuf parse error (skipping frame): {e}")
            return None

        # Step 3: validate required fields
        if not pricing_data.id or pricing_data.price == 0.0:
            return None

        result: dict = {
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

    # ──────────────────────────────────────────────────────────────────────────
    # Task 2 — Upstream receive loop (exception scope fixed)
    # ──────────────────────────────────────────────────────────────────────────

    async def _upstream_loop(self):
        """
        Persistent background task managing the single Yahoo upstream connection.

        Exception scope (Task 2):
        ┌─ outer try/except ── catches CONNECTION-level failures only
        │   → triggers backoff + circuit breaker
        │   ┌─ per-message try/except ── catches DECODE/BROADCAST failures
        │   │   → logs and continues; NEVER reconnects or increments failures
        │   └──────────────────────────────────────────────────────────────
        └─────────────────────────────────────────────────────────────────
        """
        uri = "wss://streamer.finance.yahoo.com"

        while self._is_running:

            # ── Circuit breaker ───────────────────────────────────────────
            if self.consecutive_failures >= self.max_failures:
                logger.warning(
                    f"Circuit breaker OPEN — {self.consecutive_failures} failures. "
                    f"Cooling down for {self.cooldown_period}s."
                )
                await asyncio.sleep(self.cooldown_period)
                self.consecutive_failures = 0

            # ── Outer: connection-level try/except ────────────────────────
            try:
                logger.info("Connecting to Yahoo Finance upstream WebSocket…")
                async with websockets.connect(
                    uri,
                    ping_interval=20,
                    ping_timeout=15,
                    close_timeout=10,
                ) as ws:
                    self._upstream_ws = ws
                    self.consecutive_failures = 0   # reset on successful connect
                    logger.info("✓ Connected to Yahoo upstream.")

                    await self._subscribe_all_known(ws)

                    # ── Inner receive loop ────────────────────────────────
                    async for raw_message in ws:
                        if not self._is_running:
                            break

                        # ── Per-message try/except (Task 2) ──────────────
                        # A failure here MUST NOT break the connection loop.
                        try:
                            data = self._decode_message(raw_message)
                            if data is None:
                                continue

                            raw_id: str = data["id"]
                            ticker = raw_id.replace(".NS", "").replace(".BO", "")

                            # Cache the tick
                            self.last_ticks[ticker] = data

                            # Broadcast (safe: uses snapshot copy internally)
                            await self._broadcast(ticker, data)

                        except Exception as msg_exc:
                            # Per-message error: log and skip. Do NOT reconnect.
                            logger.warning(
                                f"Per-message processing error (skipping): {msg_exc}"
                            )
                            continue  # ← continue the async for loop

            # ── Connection-level failures — trigger backoff ───────────────
            except ConnectionClosedOK:
                logger.info("Yahoo upstream closed cleanly. Reconnecting…")
                # No backoff increment — clean close is expected (e.g. daily reset)

            except ConnectionClosedError as e:
                self.consecutive_failures += 1
                delay = min(
                    self.base_delay * (2 ** (self.consecutive_failures - 1)),
                    self.max_delay
                )
                logger.error(
                    f"Yahoo upstream closed with error: {e}. "
                    f"Retry in {delay}s (failure {self.consecutive_failures}/{self.max_failures})"
                )
                await asyncio.sleep(delay)

            except Exception as e:
                self.consecutive_failures += 1
                delay = min(
                    self.base_delay * (2 ** (self.consecutive_failures - 1)),
                    self.max_delay
                )
                logger.error(
                    f"Upstream connection error: {e}. "
                    f"Retry in {delay}s (failure {self.consecutive_failures}/{self.max_failures})"
                )
                await asyncio.sleep(delay)

            finally:
                self._upstream_ws = None

    # ──────────────────────────────────────────────────────────────────────────
    # Task 4 — Lifecycle: start / graceful shutdown
    # ──────────────────────────────────────────────────────────────────────────

    def start(self):
        """Start the upstream connection background task."""
        if not self._is_running:
            self._is_running = True
            self._bg_task = asyncio.create_task(self._upstream_loop())
            logger.info("WebSocket Manager started.")

    async def shutdown(self):
        """
        Graceful shutdown (Task 4):
        1. Close every connected browser WebSocket with a proper close frame.
        2. Close the upstream Yahoo connection cleanly.
        3. Cancel the background task.

        Called from the FastAPI lifespan shutdown section in main.py.
        Logged so Render deployment logs confirm it ran.
        """
        self._is_running = False

        # ① Close all browser clients cleanly
        total_closed = 0
        for ticker, clients in list(self.active_connections.items()):
            for ws in list(clients):
                try:
                    await ws.close(code=1001, reason="Server shutting down")
                    total_closed += 1
                except Exception:
                    pass  # already dead — ignore

        logger.info(f"Graceful shutdown: closed {total_closed} browser client(s).")
        self.active_connections.clear()

        # ② Close the upstream Yahoo connection
        if self._upstream_ws is not None:
            try:
                await self._upstream_ws.close()
                logger.info("Upstream Yahoo connection closed cleanly.")
            except Exception:
                pass
            self._upstream_ws = None

        # ③ Cancel the background task
        if self._bg_task and not self._bg_task.done():
            self._bg_task.cancel()
            try:
                await self._bg_task
            except asyncio.CancelledError:
                pass
            logger.info("Upstream loop task cancelled.")


# Singleton — imported by main.py and the WebSocket route handler
manager = ConnectionManager()
