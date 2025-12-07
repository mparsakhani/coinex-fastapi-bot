import os
import time
import hashlib
import hmac
import json
import requests
from fastapi import FastAPI, Request, HTTPException

app = FastAPI()

# -----------------------------------------------------
#  Load environment variables safely
# -----------------------------------------------------
COINEX_ACCESS_ID = os.getenv("COINEX_ACCESS_ID")
COINEX_SECRET_KEY = os.getenv("COINEX_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

if not COINEX_ACCESS_ID or not COINEX_SECRET_KEY:
    raise Exception("Environment variables for API keys are missing!")

COINEX_BASE_URL = "https://api.coinex.com/v2"


# -----------------------------------------------------
#  Generate MD5 signature for CoinEx v2
# -----------------------------------------------------
def sign_v2(params: dict, secret: str):
    sorted_params = sorted(params.items())
    query = "&".join([f"{k}={v}" for k, v in sorted_params])
    raw = f"{query}&secret_key={secret}"
    signature = hashlib.md5(raw.encode()).hexdigest().upper()
    return signature


# -----------------------------------------------------
#  Place SPOT market order (CoinEx API v2)
# -----------------------------------------------------
def place_spot_order(symbol: str, side: str, amount: str):
    path = "/spot/order"
    url = COINEX_BASE_URL + path
    tonce = int(time.time() * 1000)

    params = {
        "market": symbol.upper(),
        "side": side,
        "amount": amount,
        "access_id": COINEX_ACCESS_ID,
        "tonce": tonce,
    }

    signature = sign_v2(params, COINEX_SECRET_KEY)

    headers = {
        "Content-Type": "application/json",
        "Authorization": signature
    }

    # Send request
    resp = requests.post(url, json=params, headers=headers, timeout=10)
    data = resp.json()

    if data.get("code") != 0:
        raise Exception(f"CoinEx error: {data}")

    return data["data"]


# -----------------------------------------------------
#  TradingView Webhook Endpoint
# -----------------------------------------------------
@app.post("/webhook")
async def webhook(request: Request):
    try:
        payload = await request.json()
    except:
        raise HTTPException(400, "Invalid JSON")

    # Validate secret
    if payload.get("secret") != WEBHOOK_SECRET:
        raise HTTPException(403, "Invalid secret")

    # Extract fields
    action = payload.get("action")
    symbol = payload.get("symbol")
    amount = payload.get("amount")

    if action not in ("buy", "sell"):
        raise HTTPException(400, "Invalid action")
    if not symbol or not amount:
        raise HTTPException(400, "Missing symbol or amount")

    try:
        order = place_spot_order(symbol, action, str(amount))
    except Exception as e:
        raise HTTPException(500, f"Order failed: {e}")

    return {"status": "ok", "order": order}


@app.get("/")
def home():
    return {"status": "running", "message": "CoinEx Trading Bot OK!"}
