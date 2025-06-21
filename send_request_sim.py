import requests
import json

url = "http://127.0.0.1:5000/webhook"

data = {'crypto': 'bitcoin', 'price':50000}

r = requests.post(url, data=json.dumps(data), headers={'Content-Type': 'application/json'})
print(r.content)