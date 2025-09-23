# TradeBot
Copyright (c) 2025 Jacob Ashcraft. All rights reserved.

An automated trading bot for cryptocurrency using the Kraken API, real-time price tracking, and predictive motion-based buy/sell logic.

---

## 🚀 Features (v1.2)

### ✅ Implemented

* **Trailing Stop Loss Logic**

  * Automatically sets stop loss at 1% profit if price rises.
  * Continues trailing upward if market climbs.
  * Replaces static sell limit logic.

* **Stagnant Buy Prediction Reset**

  * Resets untriggered buy limits after 24 hours.
  * Only resets if no position is currently held.

* **Refactored into Strategy & Position Classes**

  * `TradingStrategy` for price logic and stop calculations.
  * `Position_manager` for persistent state and JSON storage.

* **Consolidated and Dynamic Buy Setup**

  * Automatically sets entry, sell price, and trailing stop together.
  * Avoids race condition from multistep state setting.

* **Central Trade Call Logging**

  * Appends all trade predictions and executions into one file per coin.

* **Unified Configuration**

  * Email notifications use a single `user_email` variable.

---

## 🔜 Upcoming Improvements

* **📊 Dynamic Trade Amounts**

  * Pull balance from Kraken wallet to size trades proportionally.

* **📈 Trend-Aware Prediction Logic**

  * Enhance entry price calculations based on recent trend movements, not just local lows/highs.

* **🌍 Public Prediction Feed (Read-Only)**

  * Expose buy/sell predictions to external users with timestamps and confidence ratings.

* **🖥️ Web Dashboard**

  * Lightweight Tailscale-accessible frontend to control and monitor bot.

* **📁 Multi-Symbol Support (Optional Return)**

  * Restore functionality to scan top-movers from tracked asset list.

---
🛣️ Version 2.0 Roadmap

Version 2.0 will focus on performance, modularity, and multi-strategy scalability. The goal is to decouple the architecture into reusable components that can operate in parallel while consuming a single Kraken price feed.

🔄 Restore Functionality
	•	Restore functionality to scan top-movers from tracked asset list.

✅ Goals for v2.0

🧱 Modular Architecture

Split major classes into separate scripts/modules:
	•	TradingStrategy → strategies/trading_strategy.py
	•	PositionManager → storage/position_manager.py
	•	PriceFeed → data/price_feed.py
	•	Notifier (email, future Slack/Discord alerts) → utils/notifier.py

🔗 Centralized Data Feed
	•	Build a KrakenPriceFeed class that opens one WebSocket connection per symbol.
	•	Feed this data into multiple strategy or monitor components via threads or async queues.

♻️ Multiple Strategy Support
	•	Run different trading strategies simultaneously on the same symbol.
	•	Implement a plug-and-play interface for new strategies (BaseStrategy → CustomStrategy subclasses).

🧠 Controller Script
	•	One entry point that coordinates all modules.
	•	Loads symbols, starts feed, attaches strategies, monitors trades.

🔐 Thread-safe State Management
	•	Improve handling of shared data (e.g. prices, signals, positions).
	•	Use queue.Queue or multiprocessing.Value / Manager for concurrency.

🖥️ Optional GUI or Web Dashboard (Stretch Goal)
	•	View current position, P&L, logs, live feed.
	•	Allow toggle/start/stop of strategies.
---

## 🛠️ Setup & Usage

```bash
# Run the bot with verbose output and 1% strategy
python trade_calls.py -v -d -c SOL/USD --onepct
```

## 👤 Author

Jacob Ashcraft

Feel free to fork and contribute. Feedback and PRs welcome!

