from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from kiteconnect import KiteConnect
import os

# =====================================================
# 🔐 KITE CONFIG (SAFE — ENV VARS ONLY)
# =====================================================
API_KEY = os.getenv("mw10aq5zzfouogfs")
ACCESS_TOKEN = os.getenv("4emn4qmkj1dn9bbws17ymyyea6dxrwil")

kite = None
if API_KEY and ACCESS_TOKEN:
    try:
        kite = KiteConnect(api_key=API_KEY)
        kite.set_access_token(ACCESS_TOKEN)
    except Exception:
        kite = None

# =====================================================
# 🚀 FASTAPI APP
# =====================================================
app = FastAPI(title="ShivaTrade Algo Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # later restrict to https://shivatrade.store
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================
# 🧠 GLOBAL ALGO STATE (IN-MEMORY)
# =====================================================
algo_state = {
    "running": False,
    "position": "FLAT",
    "avg_allowed": 0,
    "avg_used": 0,
    "target": 0,
    "trail_sl": 0
}

# =====================================================
# 🩺 HEALTH CHECK (REQUIRED FOR RENDER)
# =====================================================
@app.get("/")
def health():
    return {
        "status": "OK",
        "msg": "ShivaTrade backend running 🚀"
    }

# =====================================================
# 📊 SAFE MARKET DATA API
# =====================================================
@app.get("/data")
def get_data():
    """
    Always returns JSON.
    Never crashes frontend.
    """

    if not kite:
        return {
            "error": "Kite not authenticated",
            "running": algo_state["running"],
            "position": algo_state["position"]
        }

    try:
        symbol = "NSE:INFY"  # safe equity symbol
        ltp_data = kite.ltp(symbol)
        ltp = ltp_data[symbol]["last_price"]

        signal = "BUY" if ltp > 1500 else "SELL"

        return {
            "symbol": symbol,
            "ltp": ltp,
            "signal": signal,
            "running": algo_state["running"],
            "position": algo_state["position"],
            "avg_allowed": algo_state["avg_allowed"],
            "avg_used": algo_state["avg_used"],
            "target": algo_state["target"],
            "trail_sl": algo_state["trail_sl"]
        }

    except Exception as e:
        return {
            "error": "Kite API error",
            "details": str(e),
            "running": algo_state["running"],
            "position": algo_state["position"]
        }

# =====================================================
# ▶️ START ALGO
# =====================================================
@app.post("/start")
def start_algo():
    algo_state["running"] = True
    algo_state["position"] = "ACTIVE"
    return {"status": "Algo Started 🚀"}

# =====================================================
# ⏹ STOP ALGO
# =====================================================
@app.post("/stop")
def stop_algo():
    algo_state["running"] = False
    algo_state["position"] = "FLAT"
    algo_state["avg_used"] = 0
    return {"status": "Algo Stopped ⛔"}

# =====================================================
# ⚙️ MANAGE TRADE SETTINGS
# =====================================================
@app.post("/manage")
def manage_trade(
    avg_allowed: int = 0,
    target: int = 0,
    trail_sl: int = 0
):
    algo_state["avg_allowed"] = avg_allowed
    algo_state["target"] = target
    algo_state["trail_sl"] = trail_sl

    return {
        "status": "Trade settings updated ✅",
        "state": algo_state
    }
