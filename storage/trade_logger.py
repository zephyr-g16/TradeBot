import time
import json
import os
from datetime import datetime as dt
import sys

def log_trade(symbol, price, event, owner, amount=None, note=None):
    clean_symbol = symbol.replace('/USD', '')
    os.makedirs(f"trade_data/{owner}/{clean_symbol}", exist_ok=True)
    log_file  = f"trade_data/{owner}/{clean_symbol}/trade_calls.json"
    timestamp = dt.now().isoformat()
    rawtimestamp = time.time()
    try:    
        with open(log_file, 'r') as f:
            trade_calls = json.load(f)
    except FileNotFoundError:
        trade_calls = []
    
    entry = {
        "timestamp": timestamp,
        "raw_timestamp": rawtimestamp,
        "symbol": clean_symbol,
        "price": price,
        "event": event
    }
    if amount is not None:
        if event == "buy_executed":
            entry["qty_held"] = amount
        elif event == "trailing stop sale":
            entry["balance"] = amount
    if note is not None:
        entry["note"] = note
    trade_calls.append(entry)
    
    with open(log_file, 'w') as f:
        json.dump(trade_calls, f, indent=2)

