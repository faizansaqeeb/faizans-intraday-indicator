from binance.client import Client
import pandas as pd
import numpy as np
import time
import requests

# ================= CONFIG =================
SYMBOL_LIMIT = 500
CANDLE_LIMIT = 200
HULL_LENGTH = 55
FRESH_SECONDS = 30

TIMEFRAMES = {
    "5m": Client.KLINE_INTERVAL_5MINUTE,
    "15m": Client.KLINE_INTERVAL_15MINUTE
}

SCAN_SLEEP = 8  # seconds

TELEGRAM_TOKEN = "8565575662:AAGkqeUhSI0qXzXBFDdzIgEzR4gzm2iohAw"
TELEGRAM_CHAT_ID = "2137177601"

client = Client()

# ================= TELEGRAM =================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=5)
    except:
        pass

# ================= SYMBOL FILTER =================
def get_top_symbols():
    info = client.futures_exchange_info()
    tickers = client.futures_ticker()

    vol = {t["symbol"]: float(t["quoteVolume"]) for t in tickers}

    tradable = [
        s["symbol"] for s in info["symbols"]
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
    df["close"] = df["close"].astype(float)
    return df

# ================= HULL =================
def wma(series, length):
    weights = np.arange(1, length + 1)
    return series.rolling(length).apply(
        lambda x: np.dot(x, weights) / weights.sum(), raw=True
    )

def hma(series, length):
    half = int(length / 2)
    sqrt_len = int(np.sqrt(length))
    return wma(2 * wma(series, half) - wma(series, length), sqrt_len)

# ================= SCANNER =================
alert_cache = set()

def scan():
    symbols = get_top_symbols()
    print(f"Scanning {len(symbols)} symbols")

    for symbol in symbols:
        for tf, interval in TIMEFRAMES.items():
            try:
                df = fetch_klines(symbol, interval)
                if len(df) < HULL_LENGTH + 5:
                    continue

                df["HMA"] = hma(df["close"], HULL_LENGTH)
                df["HMA_S"] = df["HMA"].shift(2)

                if df["HMA"].isna().iloc[-1]:
                    continue

                prev_trend = df["HMA"].iloc[-2] > df["HMA_S"].iloc[-2]
                curr_trend = df["HMA"].iloc[-1] > df["HMA_S"].iloc[-1]

                # FLIP DETECTED
                if prev_trend != curr_trend:
                    candle_time = df["time"].iloc[-1] / 1000
                    age = int(time.time() - candle_time)

                    if age <= FRESH_SECONDS:
                        direction = "BULLISH 🟢" if curr_trend else "BEARISH 🔴"
                        key = f"{symbol}-{tf}-{direction}"

                        if key not in alert_cache:
                            alert_cache.add(key)

                            msg = (
                                f"🚨 HULL BAND FLIP ALERT\n\n"
                                f"Coin: {symbol}\n"
                                f"Timeframe: {tf}\n"
                                f"Flip: {direction}\n"
                                f"Signal Age: {age}s\n"
                                f"⚡ Fresh Trend Shift"
                            )

                            print(msg)
                            send_telegram(msg)

            except Exception:
                continue

# ================= RUN =================
if __name__ == "__main__":
    send_telegram("✅ Hull Band Flip Scanner Started\nTF: 5m & 15m\nTop 500 USDT Perps")
    while True:
        scan()
        time.sleep(SCAN_SLEEP)
