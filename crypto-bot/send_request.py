import requests
import json

# Simulate TradingView webhook post request

url = "https://cryptonest-bot-838976878869.us-central1.run.app/webhook"
headers = {"Content-Type": "application/json"}

payload = {
    "ticker": "BTCUSD",
    "alert": "Moving up by 1% last hour",
    "server_id": 1386798662616748153,  # Replace with your server ID
    "time": "2025-07-28T15:34:00Z",
    "secret": "",
    "signal_type":"sell",
    "open": 29500,
    "close": 29600,
    "high": 29700,
    "low": 29400,
    "interval": "1h",
    "exchange": "BINANCE"
}

response = requests.post(url, headers=headers, data=json.dumps(payload))
print(response.status_code, response.text)