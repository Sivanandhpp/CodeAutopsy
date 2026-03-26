import urllib.request
import json

def post(endpoint, data):
    url = f"http://localhost:8000/api/auth/{endpoint}"
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as response:
            return response.read().decode()
    except urllib.error.HTTPError as e:
        return f"ERROR {e.code}: {e.read().decode()}"

print("login-init:", post("login-init", {"email": "test5@example.com"}))
