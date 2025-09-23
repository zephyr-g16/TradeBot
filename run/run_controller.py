from data.redis_bus import get_json, get_client, subscribe, tick_channel, publish_json
from strategies.base_strategy import TraderStatus
from storage.trade_logger import log_trade as logger
from controllers.controller import Controller
import threading
import time
import argparse
import json
import signal
from dataclasses import asdict

# commands = {
#     "cmd": "start" | "stop" | "list" | "status" | "shutdown",
#     "symbol": "SOL/USD",
#     "strategy": "base",
#     "reply_to": "controller:replies"
#     }
HB_EVERY = 60

CMD_CH = "controller:commands"
RPL_CH = "controller:replies"
HB_KEY= "heartbeat:traders:last"
CTRL_ALIVE_KEY = "controller:alive"
controller = Controller()
def shutdown(signum, frame):
    controller.controller_stop.set()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trade engine controller")
    parser.add_argument("--symbols", "-s", type=str, default="ETH/USD", help="Coin you want to track and predict trades on")
    parser.add_argument("--feed", action="store_true", help="Expose the full kraken feed")
    parser.add_argument("--timeout", "-t", type=int, default=60, help="CLI changeable timeout for trader staleness, this will be removed once the UI 1.0 is up")
    args = parser.parse_args()
    symbols = args.symbols.split(",")

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    timeout = args.timeout
    # threading.Thread(target=controller.run_forever, args=(timeout, ), daemon=True).start() # not needed, will not be used. When i make the admin console that will show a conglomerate status for all traders, using similar logic to the user dash just for literally everything
    threading.Thread(target=controller.run_control_loop, daemon=True).start()
    r = get_client()
    r.set(CTRL_ALIVE_KEY, "true")


    try:
        while not controller.controller_stop.wait(1):
            pass
        controller.shutdown()
    except KeyboardInterrupt:
        print("[CTRL] Conroller shutdown called...")
        controller.shutdown()