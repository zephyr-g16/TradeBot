import logging
import requests
import time

class Utility:
    def __init__(self):
        self.data_already_saved = False

    def safe_requests(self, url, max_retries=5):
        """Wrapper for API requests with retries limited"""
        for attempt in range(max_retries):
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    return response.json()
                else:
                    logging.warning(f"API Error {response.status_code}: {response.text}")
            except requests.RequestException as e:
                logging.error(f"Request failed: {e}")

            time.sleep(2)

    def get_24h_high_low(self, symbol):
        url = f"https://api.kraken.com/0/public/Ticker?pair={symbol}"
        data = self.safe_requests(url)
        if not data or "result" not in data:
            return None, None
        
        result = list(data["result"].values())[0]
        high_24h = float(result["h"][1])
        low_24h = float(result["l"][1])
        return high_24h, low_24h
    
    def monotonic_ms() -> int:
        return int(time.monotonic() * 1000)