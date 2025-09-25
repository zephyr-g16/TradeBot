from data.redis_bus import get_json, get_client, subscribe, tick_channel, hb_channel
from strategies.base_strategy import TradingStrategy
from controllers.trade_controller import on_message
from utils.utility import Utility
import threading
import time
import json
from dataclasses import asdict
import os
import subprocess

HB_EVERY = 60
CTRL_LIVE_KEY = "controller:alive"
    
class Controller:
    def __init__(self):
        self.threads = {}
        self.stop_flags = {}
        self.rclient = get_client()
        self._cache_lock = threading.Lock()
        self._strats: dict[str, TradingStrategy] = {}
        self.last_hb = 0
        self.controller_stop = threading.Event()
        self.last_tick: dict[str, float] = {}

    def get_or_create_strat(self, symbol: str, owner, fund_amnt: float) -> TradingStrategy:
        high_24h, low_24h = Utility().get_24h_high_low(symbol)
        tid = f"{symbol}|{owner}"
        with self._cache_lock:
            strat = self._strats.get(tid)
            if strat is None:
                strat = TradingStrategy(symbol, high_24h, low_24h, owner, fund_amnt)
                if hasattr(strat, "initialize_symbol"):
                    strat.initialize_symbol()
                self._strats[tid] = strat
            return strat
    
    def start_trader(self,owner, symbol: str, strategy_name: str, fund_amnt) -> bool:
        tid = f"{symbol}|{owner}"
        with self._cache_lock:
            t = self.threads.get(tid)
            if t and t.is_alive():
                print(f"[CTRL] {symbol} already running"); return False
        self.get_or_create_strat(symbol, owner, fund_amnt)

        stop_evt = threading.Event()
        with self._cache_lock:
            self.stop_flags[tid] = stop_evt
        th = threading.Thread(target=self.run_strategy, args=(symbol, owner, stop_evt, fund_amnt), name=f"trader-{tid}", daemon=True)
        th.start()
        with self._cache_lock:
            self.threads[tid] = th
        print(f"[CTRL] started trader for {symbol}")
        return True
    
    def stop_trader(self, owner, symbol):
        tid = f"{symbol}|{owner}"
        with self._cache_lock:
            stop_evt = self.stop_flags.get(tid)
            th = self.threads.get(tid)
            strat = self._strats.get(tid)
        
        if not th:
            print(f"[CTRL] no thread for {symbol}")
            return False
        if stop_evt:
            stop_evt.set()
        th.join(timeout=5)
        alive = th.is_alive()
        if alive:
            print(f"[CTRL] stop: {symbol} still alive after 5s")
            return False

        with self._cache_lock:
            self.threads.pop(tid, None)
            self.stop_flags.pop(tid, None)
            self._strats.pop(tid, None)
        print(f"[CTRL] Trader stopped for {symbol}")
        return True
    
    def _stop_all(self):
        with self._cache_lock:
            threads = list(self.threads.keys())

        stopped, still = [], []
        for thread in threads:
            evt = self.stop_flags.get(thread)
            th = self.threads.get(thread)

            if evt:
                evt.set()
            if th:
                th.join(timeout=1)
                if th.is_alive():
                    still.append(thread)
                else:
                    stopped.append(thread)
                    with self._cache_lock:
                        self.threads.pop(thread, None)
                        self.stop_flags.pop(thread, None)
                        self.last_tick.pop(thread, None)
                        self._strats.pop(thread, None)
        return {"ok": True, "stopped": stopped, "still_running": still}


    def run_strategy(self, symbol, owner, stop_evt, fund_amnt):
        tid = f"{symbol}|{owner}"
        self.last_tick[tid] = time.time()
        wkr_client = get_client()
        ps = wkr_client.pubsub()
        ps.subscribe(tick_channel(symbol))
        try:
            strategy = self.get_or_create_strat(symbol, owner, fund_amnt)

            def on_tick(msg: dict):
                if msg.get("symbol") != symbol:
                    return
                price = float(msg["price"])
                self.last_tick[tid] = time.time()
                on_message(strategy, price)


            print(f"[INFO] Strategy started for {tid}")

            while not stop_evt.is_set():
                now = time.time()
                if now - self.last_tick[tid] < 30:
                    msg = ps.get_message(timeout=5)
                    if not msg or msg.get("type") != "message":
                        continue
                    on_tick(json.loads(msg['data']))
                elif now - self.last_tick[tid] > 30:
                    try:
                        ps.close()
                    except Exception:
                        pass
                    ps = wkr_client.pubsub()
                    ps.subscribe(tick_channel(symbol))
                    self.last_tick[tid] = time.time()
            strategy.save_position()
            ps.unsubscribe(tick_channel(symbol))
            ps.close()
            print(f"[INFO] Strategy stopped for {symbol}")
        except Exception as e:
            print(f"[ERROR] Strategy for {tid} encountered an error: {e}")
    
    # def run_forever(self, timeout): # Heartbeat for updates on trader statuses, publishes to redis so you can subscribe and check on those statuses
    #     print(f"[HB] Heartbeat for all threads")
    #     next_hb = 0
    #     while not self.controller_stop.is_set():
    #         now = time.time()
    #         if now >= next_hb:
    #             with self._cache_lock:
    #                 items = list(self._strats.items())
    #                 last_copy = dict(self.last_tick)
                
    #             statuses = []
    #             for symbol, strat in items:
    #                 status = strat.status()
    #                 d = asdict(status)
    #                 last = last_copy.get(symbol)
    #                 age = (now - last) if last is not None else None
    #                 d["last_tick"] = last
    #                 d["tick_age_ms"] = age
    #                 d["stale"] = (age is not None and age >= timeout)
    #                 key = f"status:{symbol}"
    #                 self.rclient.set(key, json.dumps(d))
    #                 statuses.append(d)

    #             hb = {
    #                 "ts": int(now),
    #                 "symbols": [s for s, _ in items],
    #                 "statuses": statuses
    #             }
    #             self.rclient.set("heartbeat:traders:last", json.dumps(hb))
    #             next_hb = now + HB_EVERY

    #         with self._cache_lock: #staleness check
    #             symbols = list(self.threads.keys())
    #         for symbol in symbols:
    #             last = self.last_tick.get(symbol)
    #             if last is not None and (now - last) >= timeout:
    #                 print(f"[INFO] Trader for {symbol} has gone stale")
    #         time.sleep(1)

    def _handle_command(self, p: dict) -> dict:
        cmd = p.get("cmd")
        owner = p.get("owner")
        if cmd == "list":
            owned_traders = []
            with self._cache_lock:
                traders = list(self._strats.keys())
            for tid in traders:
                symbol, own = tid.split("|", 1)
                print(f"{own}")
                if own == owner:
                    owned_traders.append(symbol)
            print(f"{owned_traders}")
            return {"ok": True, "traders": owned_traders}
        
        if cmd == "start":
            sym = p.get("symbol")
            strat = p.get("strategy", "default")
            funds = p.get('fund_amnt')
            if not sym: return{"ok": False, "error": "missing symbol"}
            return {"ok": self.start_trader(owner, sym, strat, funds)}
        
        if cmd == "stop":
            sym = p.get("symbol")
            if not sym: return {"ok": False, "error": "missing symbol"}
            return {"ok": self.stop_trader(owner, sym)}
        
        if cmd == "status":
            sym = p.get("symbol")
            tid = f"{sym}|{owner}"
            if not sym: return {"ok": False, "error": "missing symbol"}
            with self._cache_lock:
                strat = self._strats.get(tid)
            if not strat:
                return {"ok": False, "error": "not running"}
            d = asdict(strat.status())
            last = self.last_tick.get(tid)
            now = time.time()
            age = (now - last) if last is not None else None
            d["last_tick"] = last
            d["tick_age"] = age
            d["stale"] = (age is not None and age >= 60)
            return {"ok": True, "status": d}
        
        if cmd == "stop_all":
            return self._stop_all()
        
        if cmd == "list all":
            with self._cache_lock:
                traders = list(self._strats.keys())
            return {"ok": True, "traders": traders}
        
        if cmd == "add_coin":
            coin = (p.get("coin") or "").strip().upper()
            if not coin or "/" not in coin:
                return {"ok": False, "error":"coin must be formatted correctly i.e. 'SOL/USD'"}
            
            symbol_file = ("/home/halodi/python_scripts/auto-trader/data/symbol_list.json")
            try:
                with open(symbol_file, 'r') as f:
                    coin_list = json.load(f)
                if coin not in coin_list:
                    coin_list.append(coin)
                    with open(symbol_file, 'w') as f:
                        json.dump(coin_list, f, indent=2)
                    subprocess.run(["/usr/bin/sudo", "-n", "/usr/bin/systemctl", "restart", "kraken_feed.service"], check=True)
            except FileNotFoundError:
                return {"ok":False, "error":"File Not Found"}
            return {"ok": True, "kraken_list": coin_list}
        
        if cmd == "get_balance":
            symbol = p.get("symbol")
            tid = f"{symbol}|{owner}"
            with self._cache_lock:
                strat = self._strats.get(tid)
            balance = strat.pm.positions["balance"]
            return {"ok": True, "balance": balance}
        
        if cmd == "shutdown":
            self.controller_stop.set()
            self.rclient.set(CTRL_LIVE_KEY, "false")
            return {"ok": True}
        
        return {"ok": False, "error": f"unknown command: {cmd}"}

    def run_control_loop(self):
        print(f"[CTRL] Controller starting")
        ctrl_client = get_client()
        ps = ctrl_client.pubsub()
        ps.subscribe("controller:commands")
        self.startup()
        self.rclient.set(CTRL_LIVE_KEY, "true")
        while not self.controller_stop.is_set():
            msg = ps.get_message(timeout=0.5)
            if not msg or msg.get("type") != "message":
                continue
            try:
                payload = json.loads(msg["data"])
                result = self._handle_command(payload)
                reply_to = payload.get("reply_to")
                if reply_to:
                    self.rclient.publish(reply_to, json.dumps(result))
            except Exception as e:
                self.rclient.set(CTRL_LIVE_KEY, "false")
                print(f"[CRTL] controller error: {e}")
    
    def shutdown(self):
        with self._cache_lock:
            active = list(self.threads.keys())
        active_traders = os.path.join("data/active_traders.json")
        try:
            with open(active_traders, 'w') as f:
                json.dump(active, f, indent=2)
        except FileNotFoundError:
            print(f"{active_traders} not found...")

    def active_update(self, tid):
        active_traders = os.path.join('data/active_traders.json')
        try:
            with open(active_traders, 'r') as f:
                active_list = json.load(f)
            active_list.append(tid)
            json.dump(active_list, f, indent=2)
        except FileNotFoundError:
            print("No active trader file found")



    def startup(self):
        trader_load_file = os.path.join("data/active_traders.json")
        try:
            with open(trader_load_file, 'r') as f:
                traders = json.load(f)
            for symown in traders:
                symbol , owner = symown.split("|", 1)
                strategy = "base"
                self.start_trader(owner, symbol, strategy, fund_amnt=None)
        except FileNotFoundError:
            print(f"File: {trader_load_file} not found...")

