import requests
import json

# Simulate TradingView webhook post request

url = "http://localhost/webhook"
headers = {"Content-Type": "application/json"}

payload = {
    "ticker": "BTCUSD",
    "alert": "Moving up by 1% last hour",
    "server_id": 1400569573278875798,  # Replace with your server ID
    "time": "2025-07-28T15:34:00Z",
    "secret": "secret",
    "open": 29500,
    "close": 29600,
    "high": 29700,
    "low": 29400,
    "interval": "1h",
    "exchange": "BINANCE"
}

response = requests.post(url, headers=headers, data=json.dumps(payload))
print(response.status_code, response.text)