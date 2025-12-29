from binance.client import Client
import pandas as pd
import numpy as np
import time
import requests

# ================= CONFIG =================
SYMBOL_LIMIT = 500
CANDLE_LIMIT = 120

ANDEAN_LENGTH = 50
SIGNAL_LENGTH = 9
FRESH_SECONDS = 60

TIMEFRAMES = {
    "5m": Client.KLINE_INTERVAL_5MINUTE,
    "15m": Client.KLINE_INTERVAL_15MINUTE
}

TELEGRAM_TOKEN = "8565575662:AAGkqeUhSI0qXzXBFDdzIgEzR4gzm2iohAw"
TELEGRAM_CHAT_ID = "2137177601"

SCAN_SLEEP = 10

client = Client()

# ================= TELEGRAM =================
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=5)
    except:
        pass

# ================= SYMBOL FILTER =================
def get_top_symbols():
    info = client.futures_exchange_info()
    tickers = client.futures_ticker()

    vol = {t["symbol"]: float(t["quoteVolume"]) for t in tickers}

    symbols = [
        s["symbol"]
        for s in info["symbols"]
        if s["quoteAsset"] == "USDT"
        and s["contractType"] == "PERPETUAL"
        and s["status"] == "TRADING"
        and s["symbol"] in vol
    ]

    symbols.sort(key=lambda x: vol[x], reverse=True)
    return symbols[:SYMBOL_LIMIT]

# ================= DATA =================
def fetch_klines(symbol, interval):
    k = client.futures_klines(symbol=symbol, interval=interval, limit=CANDLE_LIMIT)
    df = pd.DataFrame(k, columns=[
        "time","open","high","low","close","volume",
        "c1","c2","c3","c4","c5","c6"
    ])
    df[["open","close"]] = df[["open","close"]].astype(float)
    return df[["time","open","close"]]

# ================= EMA =================
def ema(arr, length):
    alpha = 2 / (length + 1)
    out = np.zeros(len(arr))
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i-1]
    return out

# ================= ANDEAN OSCILLATOR =================
def andean(df):
    alpha = 2 / (ANDEAN_LENGTH + 1)

    up1 = np.zeros(len(df))
    up2 = np.zeros(len(df))
    dn1 = np.zeros(len(df))
    dn2 = np.zeros(len(df))

    C = df["close"].values
    O = df["open"].values

    for i in range(len(df)):
        if i == 0:
            up1[i] = dn1[i] = C[i]
            up2[i] = dn2[i] = C[i] ** 2
        else:
            up1[i] = max(C[i], O[i], up1[i-1] - (up1[i-1] - C[i]) * alpha)
            up2[i] = max(C[i]**2, O[i]**2, up2[i-1] - (up2[i-1] - C[i]**2) * alpha)
            dn1[i] = min(C[i], O[i], dn1[i-1] + (C[i] - dn1[i-1]) * alpha)
            dn2[i] = min(C[i]**2, O[i]**2, dn2[i-1] + (C[i]**2 - dn2[i-1]) * alpha)

    bull = np.sqrt(np.maximum(dn2 - dn1 * dn1, 0))
    bear = np.sqrt(np.maximum(up2 - up1 * up1, 0))

    return bull, bear

# ================= SCANNER =================
alert_cache = set()

def scan():
    symbols = get_top_symbols()
    print(f"Scanning {len(symbols)} symbols...")

    for symbol in symbols:
        for tf, interval in TIMEFRAMES.items():
            try:
                df = fetch_klines(symbol, interval)

                if len(df) < 60:
                    continue

                bull, bear = andean(df)
                signal = ema(bear, SIGNAL_LENGTH)

                # === TOUCH / CROSS LOGIC ===
                proximity = abs(bear[-1] - signal[-1]) <= signal[-1] * 0.01
                cross = bear[-2] < signal[-2] and bear[-1] >= signal[-1]

                if proximity or cross:
                    ts = df["time"].iloc[-1] / 1000
                    age = int(time.time() - ts)

                    if age <= FRESH_SECONDS:
                        key = f"{symbol}-{tf}"

                        if key not in alert_cache:
                            alert_cache.add(key)

                            msg = (
                                f"🚀 ANDEAN EXPANSION ALERT\n\n"
                                f"Coin: {symbol}\n"
                                f"Timeframe: {tf}\n"
                                f"Upper Band ↔ Signal Line\n"
                                f"Signal Age: {age}s\n"
                                f"Expectation: BIG MOVE\n"
                                f"⚠️ Momentum Expansion Zone"
                            )

                            print(msg)
                            send_telegram(msg)

            except:
                continue

# ================= RUN =================
if __name__ == "__main__":
    send_telegram(
        "✅ Andean Expansion Scanner Started\n"
        "TF: 5m | 15m\n"
        "Logic: Upper Band touches Signal Line"
    )
    while True:
        scan()
        time.sleep(SCAN_SLEEP)