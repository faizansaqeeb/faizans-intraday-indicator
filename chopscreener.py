from binance.client import Client
import pandas as pd
import numpy as np
import time
import requests
from datetime import datetime

# ================= TELEGRAM =================
TELEGRAM_TOKEN = "8565575662:AAGkqeUhSI0qXzXBFDdzIgEzR4gzm2iohAw"
TELEGRAM_CHAT_ID = "2137177601"

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass

# ================= CONFIG =================
TOP_COINS = 500
CANDLE_LIMIT = 210
CHOP_LENGTH = 14

FRESHNESS = {
    "5m": 60,     # seconds
    "15m": 300
}

TIMEFRAMES = {
    "5m": Client.KLINE_INTERVAL_5MINUTE,
    "15m": Client.KLINE_INTERVAL_15MINUTE
}

INTERVAL_SECONDS = {
    "5m": 300,
    "15m": 900
}

client = Client()

# ================= SYMBOL LIST =================
def get_top_usdt_symbols(limit=500):
    tickers = client.futures_ticker()
    df = pd.DataFrame(tickers)
    df = df[df["symbol"].str.endswith("USDT")]
    df["volume"] = df["quoteVolume"].astype(float)
    df = df.sort_values("volume", ascending=False)
    return df["symbol"].head(limit).tolist()

# ================= DATA =================
def fetch_data(symbol, interval):
    klines = client.futures_klines(
        symbol=symbol,
        interval=interval,
        limit=CANDLE_LIMIT
    )

    df = pd.DataFrame(klines, columns=[
        "time","open","high","low","close","volume",
        "c1","c2","c3","c4","c5","c6"
    ])

    df[["high","low","close"]] = df[["high","low","close"]].astype(float)

    # 🔒 DROP LIVE CANDLE (TradingView match)
    return df.iloc[:-1]

# ================= ATR(1) =================
def atr_1(df):
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)

    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)

    return tr

# ================= CHOP =================
def choppiness_index(df, length=14):
    atr = atr_1(df)
    atr_sum = atr.rolling(length).sum()

    highest_high = df["high"].rolling(length).max()
    lowest_low = df["low"].rolling(length).min()

    chop = 100 * np.log10(atr_sum / (highest_high - lowest_low)) / np.log10(length)
    return chop

# ================= MEMORY =================
last_signal_time = {}

# ================= START =================
symbols = get_top_usdt_symbols(TOP_COINS)
print(f"🔍 Scanning {len(symbols)} coins...")

send_telegram("🚀 CHOP Screener Started\nMonitoring lower band (38.2)")

while True:
    now = time.time()

    for symbol in symbols:
        for tf_name, tf_interval in TIMEFRAMES.items():

            try:
                df = fetch_data(symbol, tf_interval)
                chop = choppiness_index(df)

                if len(chop.dropna()) < 2:
                    continue

                prev_chop = chop.iloc[-2]
                last_chop = chop.iloc[-1]

                # 🎯 LOWER BAND TOUCH
                if prev_chop > 38.2 and last_chop <= 38.2:

                    key = f"{symbol}_{tf_name}"
                    last_time = last_signal_time.get(key, 0)

                    if now - last_time >= FRESHNESS[tf_name]:
                        last_signal_time[key] = now

                        # ✅ Correct Signal Age calculation
                        interval_sec = INTERVAL_SECONDS[tf_name]
                        last_candle_time = df["time"].iloc[-1] / 1000  # in seconds
                        age = int(now - (last_candle_time + interval_sec))
                        if age < 0:
                            age = 0

                        message = (
                            f"🔥 <b>CHOP LOWER BAND TOUCH</b>\n\n"
                            f"🪙 <b>Coin:</b> {symbol}\n"
                            f"⏱ <b>Timeframe:</b> {tf_name}\n"
                            f"📉 <b>CHOP:</b> {last_chop:.2f}\n"
                            f"🕒 <b>Signal Age:</b> {age} sec\n\n"
                            f"⚡ Trend may be starting"
                        )

                        print(message.replace("<b>", "").replace("</b>", ""))
                        send_telegram(message)

            except Exception as e:
                print(f"Error for {symbol} {tf_name}: {e}")
                continue

    time.sleep(5)