from binance.client import Client
import pandas as pd
import numpy as np
import time
import requests
from datetime import datetime, timezone

# ================= CONFIG =================
SYMBOL_LIMIT = 500
CANDLE_LIMIT = 120
LENGTH = 50
SIGNAL_LENGTH = 9
FRESH_SECONDS = 60

TIMEFRAMES = {
    "5m": Client.KLINE_INTERVAL_5MINUTE,
    "10m": "10m",   # custom via resample
    "15m": Client.KLINE_INTERVAL_15MINUTE
}

TELEGRAM_TOKEN = "8565575662:AAGkqeUhSI0qXzXBFDdzIgEzR4gzm2iohAw"
TELEGRAM_CHAT_ID = "2137177601"

SCAN_SLEEP = 8  # seconds between scan rounds

client = Client()

# ================= TELEGRAM =================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
    try:
        requests.post(url, data=data, timeout=5)
    except:
        pass

# ================= SYMBOL FILTER =================
def get_top_symbols():
    info = client.futures_exchange_info()
    tickers = client.futures_ticker()

    vol = {t["symbol"]: float(t["quoteVolume"]) for t in tickers}

    tradable = [
        s["symbol"]
        for s in info["symbols"]
        if s["quoteAsset"] == "USDT"
        and s["contractType"] == "PERPETUAL"
        and s["status"] == "TRADING"
        and s["symbol"] in vol
    ]

    tradable.sort(key=lambda x: vol[x], reverse=True)
    return tradable[:SYMBOL_LIMIT]

# ================= DATA =================
def fetch_klines(symbol, interval):
    k = client.futures_klines(symbol=symbol, interval=interval, limit=CANDLE_LIMIT)
    df = pd.DataFrame(k, columns=[
        "time","open","high","low","close","volume",
        "c1","c2","c3","c4","c5","c6"
    ])
    df[["open","close"]] = df[["open","close"]].astype(float)
    return df[["time","open","close"]]

def resample_10m(df):
    df = df.copy()
    df["time"] = pd.to_datetime(df["time"], unit="ms")
    df.set_index("time", inplace=True)

    r = df.resample("10min").agg({
        "open": "first",
        "close": "last"
    }).dropna()

    r.reset_index(inplace=True)
    r["time"] = r["time"].astype(np.int64) // 10**6
    return r

# ================= ANDEAN =================
def andean(df):
    alpha = 2 / (LENGTH + 1)

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
    print(f"Scanning {len(symbols)} tradable USDT perpetual symbols")

    for symbol in symbols:
        for tf, interval in TIMEFRAMES.items():
            try:
                if tf == "10m":
                    df5 = fetch_klines(symbol, Client.KLINE_INTERVAL_5MINUTE)
                    df = resample_10m(df5)
                else:
                    df = fetch_klines(symbol, interval)

                if len(df) < 30:
                    continue

                bull, bear = andean(df)

                # compression detection
                dist_now = abs(bull[-1] - bear[-1])
                dist_prev = abs(bull[-2] - bear[-2])

                if dist_now < dist_prev * 0.35:
                    ts = df["time"].iloc[-1] / 1000
                    age = int(time.time() - ts)

                    if age <= FRESH_SECONDS:
                        bias = "BULLISH" if bull[-1] > bear[-1] else "BEARISH"
                        key = f"{symbol}-{tf}-{bias}"

                        if key not in alert_cache:
                            alert_cache.add(key)

                            msg = (
                                f"🔥 ANDEAN COMPRESSION\n\n"
                                f"Coin: {symbol}\n"
                                f"Timeframe: {tf}\n"
                                f"Bias: {bias}\n"
                                f"Signal Age: {age} sec\n"
                                f"Status: PRE-EXPANSION\n"
                                f"⚠️ Early Entry Zone"
                            )

                            print(msg)
                            send_telegram(msg)

            except Exception as e:
                continue

# ================= RUN =================
if __name__ == "__main__":
    send_telegram("✅ Andean Compression Scanner Started\nTF: 5m | 10m | 15m\nTop 500 USDT Perps")
    while True:
        scan()
        time.sleep(SCAN_SLEEP)