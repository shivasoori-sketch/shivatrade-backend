def run_strategy(ltp):
    if ltp > 200:
        return {
            "signal": "BUY",
            "sl": round(ltp - 10, 2),
            "target": round(ltp + 20, 2)
        }
    return {
        "signal": "HOLD",
        "sl": None,
        "target": None
    }
