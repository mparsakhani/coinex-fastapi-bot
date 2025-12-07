from fastapi import FastAPI, Request, HTTPException
import requests
import time
import hashlib
import os

app = FastAPI()

# ---------- ENV ----------
COINEX_BASE_URL = "https://api.coinex.com/v2"
ACCESS_ID = os.getenv("COINEX_ACCESS_ID")
SECRET_KEY = os.getenv("COINEX_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

if not ACCESS_ID or not SECRET_KEY or not WEBHOOK_SECRET:
    raise Exception("❌ ENV variables (ACCESS_ID / SECRET_KEY / WEBHOOK_SECRET) not set")


# ---------- SIGN V2 ----------
def sign_v2(params: dict, secret: str) -> str:
    sorted_params = sorted(params.items())
    query = "&".join([f"{k}={v}" for k, v in sorted_params])
    raw = f"{query}&secret_key={secret}"
    return hashlib.md5(raw.encode()).hexdigest()


# ---------- ORDER FUNCTION ----------
def place_spot_order(symbol: str, side: str, amount: str, order_type="market"):
    path = "/spot/order"
    url = COINEX_BASE_URL + path
    tonce = int(time.time() * 1000)

    params = {
        "market": symbol.upper(),
        "side": side,
        "amount": amount,
        "type": order_type,          # market / limit
        "access_id": ACCESS_ID,
        "tonce": tonce
    }

    signature = sign_v2(params, SECRET_KEY)

    headers = {
        "Content-Type": "application/json",
        "Authorization": signature
    }

    resp = requests.post(url, json=params, headers=headers, timeout=10)
    
    try:
        data = resp.json()
    except:
        raise Exception(f"❌ Invalid JSON from CoinEx: {resp.text}")

    if data.get("code") != 0:
        raise Exception(f"❌ CoinEx error: {data}")

    return data["data"]


# ---------- WEBHOOK ----------
@app.post("/webhook")
async def tradingview_webhook(request: Request):
    try:
        payload = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Validate webhook secret
    if payload.get("secret") != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")

    action = payload.get("action")
    symbol = payload.get("symbol")
    amount = payload.get("amount", "0.001")
    order_type = payload.get("order_type", "market")

    if action not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail="Invalid action")

    if not symbol or not amount:
        raise HTTPException(status_code=400, detail="Missing symbol or amount")

    # Execute order
    try:
        order = place_spot_order(
            symbol=str(symbol),
            side=str(action),
            amount=str(amount),
            order_type=str(order_type)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Order failed: {e}")

    return {"status": "ok", "order": order}


# ---------- ROOT ----------
@app.get("/")
def root():
    return {"status": "running"}
