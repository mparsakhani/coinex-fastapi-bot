import time
import hmac
import hashlib
import json
import os

COINEX_BASE_URL = "https://api.coinex.com/v2"
ACCESS_ID = os.getenv("COINEX_ACCESS_ID")
SECRET_KEY = os.getenv("COINEX_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

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
    
def place_spot_order(symbol: str, side: str, amount: str):
    """
    Place MARKET order on CoinEx API v2
    """
    path = "/order/put_market"
    url = COINEX_BASE_URL + path

    tonce = int(time.time() * 1000)

    params = {
        "market": symbol.upper(),   # IMPORTANT
        "side": side,               # "buy" or "sell"
        "amount": amount,
        "access_id": ACCESS_ID,
        "tonce": tonce
    }

    signature = sign_v2(params, SECRET_KEY)

    headers = {
        "Content-Type": "application/json",
        "Authorization": signature
    }

    resp = requests.post(url, json=params, headers=headers)
    data = resp.json()

    if data.get("code") != 0:
        raise Exception(f"CoinEx ERROR: {data}")

    return data["data"]



@app.post("/webhook")
async def tradingview_webhook(request: Request):
    try:
        payload = await request.json()
        print("Received payload:", payload)

    except Exception as e:
        print("JSON error:", e)
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # چک کردن secret
    try:
        if payload.get("secret") != WEBHOOK_SECRET:
            print("Invalid secret received:", payload.get("secret"))
            raise HTTPException(status_code=403, detail="Invalid secret")
    except Exception as e:
        print("Secret error:", e)
        import traceback; traceback.print_exc()
        raise

    # گرفتن اطلاعات
    try:
        action = payload.get("action")
        symbol = payload.get("symbol")
        amount = payload.get("amount")
        order_type = payload.get("order_type", "market")
        print("Parsed data:", action, symbol, amount, order_type)
    except Exception as e:
        print("Payload parsing error:", e)
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=400, detail="Bad payload")

    # اجرای سفارش
    try:
        order = place_spot_order(
            symbol=str(symbol),
            side=str(action),
            amount=str(amount),
            order_type=str(order_type),
        )
        print("Order response:", order)

    except Exception as e:
        print("ORDER ERROR:", e)
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Order failed: {e}")

    return {"status": "ok", "order": order}


@app.get("/")
async def root():
    return {"status": "running"}
