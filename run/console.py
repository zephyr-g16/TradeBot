from data.redis_bus import get_client
from ui.command_helper import send_cmd, get_heartbeat
import argparse
import threading
import time
import sys
import os
import subprocess
import random

HB_EVERY = 60

CMD_CH = "controller:commands"
RPL_CH = "controller:replies"
HB_KEY= "heartbeat:traders:last"
CTRL_ALIVE_KEY = "controller:alive"
CONTROLLER_ID = os.getenv("CONTROLLER_ID", "alpha")

command_list = ["start", "stop", "status", "list", "heartbeat", "quit"]

def launch_controller(controller_id = CONTROLLER_ID) -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "start", f"controller@{controller_id}"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"[console] Systemctl start failed: {e.stderr.strip()}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trade engine controller")
    parser.add_argument("--symbols", "-s", type=str, default="ETH/USD", help="Coin you want to track and predict trades on")
    parser.add_argument("--feed", action="store_true", help="Expose the full kraken feed")
    parser.add_argument("--timeout", "-t", type=int, default=60, help="CLI changeable timeout for trader staleness, this will be removed once the UI 1.0 is up")
    args = parser.parse_args()
    symbols = args.symbols.split(",")
    symbol_list = [
        "SOL/USD",
        "ETH/USD",
        "XBT/USD",
        "XDG/USD",
        "LINK/USD",
        "XCN/USD"
    ]
    strat_list = ["base"]

    timeout = args.timeout
    r = get_client()
    tag = random.randint(1, 100000)
    user_name = input(f"""
        
Hello, welcome to TradeBot. Can I get your name?: 
        
    """)
    user_id = f"{user_name}_{tag}"
    alive = r.get("controller:alive")
    if alive == "true":
        print(f"""Hello {user_name}, The controller is up and running""")
    else:
        while True:
            decision = input(f"Conroller is not running, would you like to start it? (yes/no): ").lower()
            if decision != "yes" or "no":
                print("Sorry only a yes or no answer works, please try again")
            if decision == "no":
                break
            if decision == "yes":
                if launch_controller("alpha"):
                    print("started controller@alpha")
                    for _ in range(20):
                        v = r.get(CTRL_ALIVE_KEY)
                        if isinstance(v, (bytes,bytearray)):
                            v = v.decode()
                        if v == "true":
                            print("Controller is live")
                            break
                        time.sleep(0.3)
                else:
                    print(f"Could not start systemnd controller service, contact an administrator...")

    while True:
        print("""
    Menu:
        
[Start]   [Stop]
        
[Status]  [Heartbeat]

     [Quit]
        """)
        choice = input("Selection: ").strip().lower()
        if choice in command_list:
#             if choice == "list":
#                 response = send_cmd({"cmd":"list","owner":user_id, "reply_to":RPL_CH})
#                 symbols = response.get("traders")
#                 print(f"""
#     {",".join(symbols)}
# """)
            if choice == "start":
                cancelled = False
                while True:
                    print(f"""Please choose a symbol: 
                        
{symbol_list}
[exit]
""")
                    symbol_choice = input("Please type the full symbol name, or exit: ").upper()
                    if symbol_choice in symbol_list:
                        break
                    if symbol_choice != "EXIT":
                        print(f"Unknown Symbol: {symbol_choice}, please try again")
                    else:
                        cancelled = True
                        break
                if cancelled:
                    continue
                while True:
                    print("""Please select a strategy: 
                        [base]
                        new strategy coming soon ... """)
                    strat_choice = input("Selection: ")
                    if strat_choice in strat_list:
                        break
                    if strat_choice.lower() != "exit":
                        print(f"Unknown strategy: {strat_choice}, try again")
                    else:
                        cancelled = True
                        break
                if cancelled:
                    continue
                print(send_cmd({"cmd":"start","owner":user_id, "symbol": symbol_choice, "strategy":strat_choice, "reply_to":RPL_CH}))
            if choice == "stop":
                cancelled = False
                raw_list = send_cmd({"cmd":"list","owner":user_id, "reply_to":RPL_CH})
                symbols = raw_list.get("traders")
                while True:
                    print(f"""What symbol would you like to stop?:
""")
                    print(f"""  {",".join(symbols)}
""")
                    symbol_choice = input("Please type the full symbol: ").upper()
                    if symbol_choice in symbol_list:
                        break
                    if symbol_choice != "EXIT":
                     print(f"Unknown symbol: {symbol_choice}, try again.")    
                    else:
                        cancelled = True
                        break
                if cancelled:
                    continue
                print(send_cmd({"cmd": "stop","owner":user_id, "symbol":symbol_choice, "reply_to":RPL_CH}))
            if choice == "status":
                cancelled = False
                raw_list = send_cmd({"cmd":"list", "owner":user_id, "reply_to":RPL_CH})
                symbols = raw_list.get("traders")
                while True:
                    print(f"""What symbol would you like the status for?: 
    {",".join(symbols)}
""")
                    symbol_choice = input("Please type the full symbol: ").upper()
                    if symbol_choice in symbol_list:
                        break
                    if symbol_choice != "EXIT":
                        print(f"Unknown symbol: {symbol_choice}, try again")
                    else:
                        cancelled = True
                        break
                if cancelled:
                    continue
                print(send_cmd({"cmd":"status","owner":user_id, "symbol":symbol_choice, "reply_to":RPL_CH}))
            if choice == "heartbeat":
                print(get_heartbeat())
            if choice == "quit":
                break
        else:
            print(f"Error, unknown command: {choice}")
        time.sleep(0.5)