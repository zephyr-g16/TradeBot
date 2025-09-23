import json, redis
from typing import Callable

def get_client(host: str = "localhost", port: int = 6379) -> redis.Redis:
    return redis.Redis(host=host, port=port, decode_responses=True)

def publish_json(r: redis.Redis, channel: str, obj: dict) -> None:
    r.publish(channel, json.dumps(obj))

def set_json(r: redis.Redis, key: str, obj: dict) -> None:
    r.set(key, json.dumps(obj))

def tick_channel(symbol: str) -> str:
    return f"ticks:{symbol}"

def hb_channel():
    return f"heartbeat:traders"

def get_json(r: redis.Redis, key: str):
    raw = r.get(key)
    return json.loads(raw) if raw else None

def subscribe(r: redis.Redis, channel: str, on_message: Callable[[dict], None], timeout: int = 1):
    ps = r.pubsub()
    ps.subscribe(channel)
    while True:
        msg = ps.get_message(timeout=timeout)
        if msg and msg.get("type") == "message":
            on_message(json.loads(msg["data"]))