import time
import json

class Position_manager:
    def __init__(self, symbol, owner):
        self.symbol = symbol.replace('/USD', '')
        self.filepath = f"trade_data/{owner}/{self.symbol}/position_info.json"
        self.positions = {}
        # self.load_from_file()

    def initialize_symbol(self):
            self.positions = {
                "position_open": False,
                "entry_price": None,
                "sell_price": None,
                "last_sale_price": None,
                "buy_limit_set": False,
                "sell_limit_set": False,
                "last_trade_time": 0,
                "trailing_stop": None,
                "brekeven_override": False,
                "profit_loss_protection": False,
                "buy_prediction_timestamp": None,
                "buy_prediction_resets": 0,
                "qty_held": None,
                "balance": None,
                "funds_config": None
            }

    def open_position(self, entry_price, trailing_stop):
        self.positions["position_open"] = True
        self.positions["entry_price"] = entry_price
        self.positions["buy_limit_set"] = False
        self.positions["trailing_stop"] = trailing_stop

    def close_position(self, sell_price):
        self.positions["position_open"] = False
        self.positions["sell_price"] = None
        self.positions["sell_limit_set"] = False
        self.positions["last_sale_price"] = sell_price
        self.positions["trailing_stop"] = None
    
    def set_buy_limit(self, entry_price):
        self.positions["entry_price"] = entry_price
        self.positions["buy_limit_set"] = True
        self.positions["buy_prediction_timestamp"] = time.time()
    
    def set_sell_limit(self, sell_price):
        self.positions["sell_price"] = sell_price
        self.positions["sell_limit_set"] = True
    
    def reset_limits(self):
        self.positions["buy_limit_set"] = False
        self.positions["entry_price"] = None
        self.positions["buy_prediction_timestamp"] = None
        self.positions["buy_prediction_resets"] += 1
    
    def get_position_state(self):
        return self.positions
    
    def calculate_buy_qty(self):
        self.positions["qty_held"] = self.positions["balance"] / self.positions["entry_price"]
        return self.positions["qty_held"]
    
    def calculate_sell_total(self, sell_price):
        self.positions["balance"] = self.positions["qty_held"] * sell_price
        return self.positions["balance"]

    def is_position_open(self):
        return self.positions["position_open"]

    def has_buy_limit(self):
        return self.positions["buy_limit_set"]
    
    def has_sell_limit(self):
        return self.positions["sell_limit_set"]
    
    def update_trade_time(self, timestamp):
        self.positions["last_trade_time"] = timestamp
    
    def prediction_age(self):
        ts = self.positions.get("buy_prediction_timestamp")
        if ts:
            return time.time() - ts
        return None
    
    def save_to_file(self):
        with open(self.filepath, 'w') as f:
            json.dump(self.positions, f, indent=2)
    
    def smart_save(self):
        state = self.positions

        if state["position_open"]:
            print(f"Saving active position for {self.symbol}")
            self.save_to_file()
        
        elif state["buy_limit_set"] and not state["position_open"]:
            print(f"Saving buy limit for {self.symbol}")
            self.save_to_file()
        
        elif not state["position_open"] and not state["buy_limit_set"]:
            print(f"No prediction or position held for {self.symbol}. Resetting state...")
            self.positions["entry_price"] = None
            self.positions["sell_limit_set"] = False
            self.positions["sell_price"] = None
            self.positions["buy_limit_set"] = False
            self.positions["buy_limit"] = None
            self.positions["buy_prediction_timestamp"] = None
            self.save_to_file()

    
    def load_from_file(self):
        default_state = {
            "position_open": False,
            "entry_price": None,
            "sell_price": None,
            "last_sale_price": None,
            "buy_limit_set": False,
            "sell_limit_set": False,
            "last_trade_time": 0,
            "trailing_stop": None,
            "brekeven_override": False,
            "profit_loss_protection": False,
            "buy_prediction_timestamp": None,
            "buy_prediction_resets": 0,
            "qty_held": None,
            "balance": None,
            "funds_config": None
            }
        try:
            with open(self.filepath, 'r') as f:
                self.positions = json.load(f)
        except FileNotFoundError:
            self.initialize_symbol()
            print("No position file found, initializing...")
        
        for key, value in default_state.items():
            self.positions.setdefault(key, value)