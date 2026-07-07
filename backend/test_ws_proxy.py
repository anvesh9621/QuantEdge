import asyncio
import websockets
import json

async def mock_client(client_id, ticker):
    uri = f"ws://localhost:8000/ws/prices/{ticker}"
    try:
        async with websockets.connect(uri) as ws:
            print(f"Client {client_id} connected to {ticker}")
            while True:
                msg = await ws.recv()
                data = json.loads(msg)
                print(f"[Client {client_id}] Received tick for {data.get('id')}: {data.get('price')}")
    except Exception as e:
        print(f"Client {client_id} error: {e}")

async def main():
    print("Starting 3 simulated clients for RELIANCE...")
    # Start 3 clients concurrently
    tasks = [
        mock_client(1, "RELIANCE"),
        mock_client(2, "RELIANCE"),
        mock_client(3, "HDFCBANK"),
    ]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
