from storage.trade_logger import log_trade
from strategies.base_strategy import TradingStrategy
from datetime import datetime as dt

def on_message(strat: TradingStrategy, message):
    symbol = strat.symbol
    pm = strat.pm
    price = float(message)

    if strat.last_price is None:
        strat.last_price = price
        strat.local_high = strat.high_24h
        strat.local_low = strat.low_24h
        strat.trend_state = None
        strat.last_sale_price = None
        strat.trailing_stop = None
        return
    
    if not pm.is_position_open() and not pm.has_buy_limit() and not pm.has_sell_limit():
        print(f"No position held for {symbol}, calculating buy limit prediction...")
        strat.entry_price = strat.generate_buy_price()
        print(f"Place buy order for {symbol} at ${strat.entry_price}")
        pm.set_buy_limit(strat.entry_price)
        log_trade(symbol, strat.entry_price, "buy_prediction", strat.owner)
        strat.save_position()

    elif pm.is_position_open() and not pm.has_sell_limit():
        print(f"Position opened for {symbol}, calculating sell limit prediction...")
        strat.sell_price = strat.generate_sell_price()
        print(f"Place sell order for {symbol} at ${strat.sell_price}")
        pm.set_sell_limit(strat.sell_price)
        log_trade(symbol, strat.sell_price, "sell_prediction", strat.owner)
        strat.save_positio()
    
    if pm.has_buy_limit():
        if strat.should_buy(price) and not pm.is_position_open():
            print(f"Buy order executed for {symbol} at ${strat.entry_price}")
            strat.last_sale_price = None
            strat.trailing_stop = strat.entry_price * (1 - (strat.stop_loss_threshold/100))
            pm.open_position(strat.entry_price, strat.trailing_stop)
            if strat.pm.positions["funds_config"] is not None:
                qty_held = pm.calculate_buy_qty()
                strat.balance = None
                log_trade(symbol, strat.entry_price, "buy_executed", strat.owner, qty_held)
                strat.save_position()
            else:
                log_trade(symbol, strat.entry_price, "buy_executed", strat.owner)
                strat.save_position()
    
    elif pm.has_sell_limit():
        if strat.should_sell(price) and pm.is_position_open():
            print(f"Sell executed for {symbol} because of trailing stop at ${strat.trailing_stop}")
            if strat.pm.positions["funds_config"] is not None:
                strat.balance = pm.calculate_sell_total(strat.sell_price)
            pm.close_position(strat.trailing_stop)
            qty_held = None
            log_trade(symbol, strat.trailing_stop, "trailing stop sale", strat.owner, strat.balance)
            strat.save_position()
    
    strat.update_trend_extremes(price)
    if pm.is_position_open():
        strat.update_trailing_stop(price)

    if strat.trend_state == "up" or strat.trend_state is None:
        if price > strat.last_price:
            strat.trend_state = "up"
        if price > strat.local_high:
            strat.local_high = price
        if price > strat.high_24h:
            strat.high_24h = price
        if price < strat.last_price:
            strat.trend_state = "down"     
    
    if strat.trend_state == "down":
        if price < strat.local_low:
            strat.local_low = price
        if price < strat.low_24h:
            strat.low_24h = price
        if price > strat.last_price:
            strat.trend_state = "up"
    
    strat.last_price = price
    print(f"{symbol} | price: ${price:.4f} | Trend: {strat.trend_state}")
    age = strat.pm.prediction_age()
    if not strat.pm.is_position_open() and age > 86400:
        print(f"Buy prediction stale, resetting...")
        strat.pm.reset_limits()
        log_trade(symbol, None, "prediction reset", strat.owner)
