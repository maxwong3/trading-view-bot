import requests
import json

# This script simulates sending a request for the bot to receive. This can be deleted after TradingView webhooks are implemented.

url = "http://127.0.0.1:8000/webhook"

data = {'crypto': 'bitcoin', 'price':50000}

r = requests.post(url, data=json.dumps(data), headers={'Content-Type': 'application/json'})
print(r.content)