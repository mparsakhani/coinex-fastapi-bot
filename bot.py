import time
import hmac
import hashlib
import json
import os

import requests
from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv

# Load env vars (useful if you run it locally)
load_dotenv()

COINEX_BASE_URL = "https://api.coinex.com/v2"
ACCESS_ID = os.getenv("COINEX_ACCESS_ID")
SECRET_KEY = os.getenv("COINEX_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

if not ACCESS_ID or not SECRET_KEY or not WEBHOOK_SECRET:
    print("WARNING: Missing one of COINEX_ACCESS_ID / COINEX_SECRET_KEY / WEBHOOK_SECRET")

app = FastAPI()


def sign_request(method: str, path: str, body: dict | None, timestamp_ms: str) -> str:
    """
    CoinEx v2 signature:
    prepared_str = method + request_path + body(optional) + timestamp
    then HMAC-SHA256 with secret_key
    """
    method = method.upper()

    if body:
        body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    else:
        body_str = ""

    prepared_str = f"{method}{path}{body_str}{timestamp_ms}"

    signature = hmac.new(
        SECRET_KEY.encode("utf-8"),
        prepared_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return signature


def place_spot_order(symbol: str, side: str, amount: str, order_type: str = "market"):
    """
    Place a SPOT market order on CoinEx.
    """
    path = "/spot/order"
    url = COINEX_BASE_URL + path

    body = {
        "market": symbol,          # e.g. "BTCUSDT"
        "market_type": "SPOT",
        "side": side,              # "buy" or "sell"
        "type": order_type,        # "market"
        "amount": amount,          # string, e.g. "0.001"
    }

    timestamp_ms = str(int(time.time() * 1000))
    signature = sign_request("POST", path, body, timestamp_ms)

    headers = {
        "Content-Type": "application/json",
        "X-COINEX-KEY": ACCESS_ID,
        "X-COINEX-SIGN": signature,
        "X-COINEX-TIMESTAMP": timestamp_ms,
    }

    resp = requests.post(url, headers=headers, json=body, timeout=10)
    data = resp.json()

    # CoinEx returns {"code":0,"data":{...},"message":"OK"} on success
    if data.get("code") != 0:
        raise Exception(f"CoinEx error: {data}")

    return data["data"]


@app.post("/webhook")
async def tradingview_webhook(request: Request):
    # 1) دریافت JSON
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # 2) چک کردن secret
    if payload.get("secret") != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")

    # 3) گرفتن پارامترها
    action = payload.get("action")
    symbol = payload.get("symbol")
    amount = payload.get("amount")
    order_type = payload.get("order_type", "market")

    if action not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail="Invalid action")

    if not symbol or amount is None:
        raise HTTPException(status_code=400, detail="Missing symbol or amount")

    try:
        order = place_spot_order(
            symbol=str(symbol),
            side=str(action),
            amount=str(amount),
            order_type=str(order_type),
        )
    except Exception as e:
        # اگر کوینکس خطا داد، متنش رو برمی‌گردونیم
        raise HTTPException(status_code=500, detail=f"Order failed: {e}")

    return {"status": "ok", "order": order}


@app.get("/")
async def root():
    return {"status": "running"}
