from typing import Callable
import websocket
import json
import threading
import os
import time
from datetime import datetime as dt
from data.redis_bus import get_client, publish_json, set_json

_r = None
def _rds():
    global _r
    if _r is None:
        _r = get_client()
    return _r


class KrakenPriceFeed:
    def __init__(self, symbols: list[str]):
        self.symbols = symbols
        self.subscribers = []
        self.latest_prices = {}

    def subscribe(self, callback: Callable[[str, float], None]):
        """Register a callback that receives price updates"""
        self.subscribers.append(callback)

    def unsubscribe(self, callback):
        self.subscribers.remove(callback)
    
    def _notify_subscribers(self, symbol: str, price: float):
        for callback in self.subscribers:
            callback(symbol, price)
    
    def publish_tick(self, symbol: str, price: float):
        msg = {"ts": int(time.time()*1000), "symbol": symbol, "price": float(price)}
        r = _rds()
        publish_json(r, f"ticks:{symbol}", msg)
        set_json(r, f"lvc:{symbol}", msg)

    def log(self, event):
        log_dir = "/home/halodi/python_scripts/auto-trader/data/feed_logs"
        os.makedirs(log_dir, exist_ok=True)
        log_file = f"{log_dir}/feed_log.json"
        timestamp = dt.now().isoformat()
        try:
            with open(log_file, 'r') as f:
                logs = json.load(f)
        except FileNotFoundError:
            logs = []
        
        entry = {
            "event": str(event),
            "timestamp": timestamp
        }
        logs.append(entry)
        with open(log_file, 'w') as f:
            json.dump(logs, f, indent=2)

    
    def start(self):
        def on_open(ws):
            for symbol in self.symbols:
                ws.send(json.dumps({
                    "event": "subscribe",
                    "pair": [symbol],
                    "subscription": {"name": "trade"}
                }))
        def on_message(ws, message):
            data = json.loads(message)
            if isinstance(data, list) and data[-2] == "trade":
                symbol = data[-1].upper()
                    
                trades = data[1]
                if not trades:
                    return
                price = float(trades[0][0])
                self._notify_subscribers(symbol, price)
                self.publish_tick(symbol, price)
                self.latest_prices[symbol] = price
            else:
                return

        def on_error(ws, error):
            print("Websocket error:", error)
            # self.log(f"Websocket error: {error}")

        def on_close(ws, code, msg):
            print("Websocket Closed")
            # self.log("Websocket closed")

        ws_url = f"wss://ws.kraken.com"
        def run_ws():
            while True:
                ws = websocket.WebSocketApp(
                    ws_url,
                    on_open=on_open,
                    on_message=on_message,
                    on_error=on_error,
                    on_close=on_close
                )
                ws.run_forever(ping_interval=40, ping_timeout=20)
                print("[INFO] Websocket disconnected, reconnecting...")
                # self.log("[INFO] Websocket disconnecter, reconnecting...")
                time.sleep(5)
        wst = threading.Thread(target=run_ws, daemon=True)
        wst.start()
    
def expose_feed(symbol, price):
        print(f"{symbol}: {price}")


if __name__ == "__main__":
    with open("data/symbol_list.json") as f:
        symbol_list = json.load(f)
    feed = KrakenPriceFeed(symbol_list)
    feed.start()
    feed.subscribe(expose_feed)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping feed...")