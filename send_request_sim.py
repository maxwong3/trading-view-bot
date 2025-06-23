import requests
import json

# This script simulates sending a request for the bot to receive. This can be deleted after TradingView webhooks are implemented.

url = "https://trading-view-bot-0s4c.onrender.com/webhook"

data = {'crypto': 'bitcoin', 'price':50000}

r = requests.post(url, data=json.dumps(data), headers={'Content-Type': 'application/json'})
print(r.content)