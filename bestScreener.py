from binance.client import Client
import pandas as pd
import numpy as np
import time
import requests
import math

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
EMA_FAST = 9
EMA_SLOW = 20

TIMEFRAMES = {
    "5m": Client.KLINE_INTERVAL_5MINUTE,
    "15m": Client.KLINE_INTERVAL_15MINUTE
}

INTERVAL_SECONDS = {
    "5m": 300,
    "15m": 900
}

FRESHNESS_LIMIT = 25  # seconds
MIN_SUCCESS_RATE = 20

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
    klines = client.futures_klines(symbol=symbol, interval=interval, limit=CANDLE_LIMIT)
    df = pd.DataFrame(klines, columns=[
        "time","open","high","low","close","volume",
        "c1","c2","c3","c4","c5","c6"
    ])
    df[["open","high","low","close"]] = df[["open","high","low","close"]].astype(float)
    return df.iloc[:-1]  # drop live candle

# ================= INDICATORS =================
def ema(series, length):
    return series.ewm(span=length, adjust=False).mean()

def atr(df, length=14):
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/length, adjust=False).mean()

def adx(df, length=14):
    high, low, close = df["high"], df["low"], df["close"]
    up = high.diff()
    down = -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)

    tr = atr(df, length)
    plus_di = 100 * pd.Series(plus_dm).ewm(alpha=1/length).mean() / tr
    minus_di = 100 * pd.Series(minus_dm).ewm(alpha=1/length).mean() / tr

    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    return dx.ewm(alpha=1/length).mean()

def choppiness_index(df, length=14):
    atr1 = atr(df, 1)
    atr_sum = atr1.rolling(length).sum()
    highest_high = df["high"].rolling(length).max()
    lowest_low = df["low"].rolling(length).min()
    return 100 * np.log10(atr_sum / (highest_high - lowest_low)) / np.log10(length)

def rsi(series, length=14):
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/length).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/length).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# ================= SCORING =================
def success_rate(direction, df):
    score = 0

    adx_val = adx(df).iloc[-1]
    chop_val = choppiness_index(df).iloc[-1]
    rsi_val = rsi(df["close"]).iloc[-1]

    ema9 = ema(df["close"], 9).iloc[-1]
    ema21 = ema(df["close"], 21).iloc[-1]
    ema50 = ema(df["close"], 50).iloc[-1]
    ema200 = ema(df["close"], 200).iloc[-1]

    atr_now = atr(df).iloc[-1]
    atr_prev = atr(df).iloc[-5]

    # ADX
    if adx_val < 15: return 0
    elif adx_val < 20: score += 5
    elif adx_val < 25: score += 15
    elif adx_val < 35: score += 25
    else: score += 30

    # CHOP
    if chop_val > 61.8: return 0
    elif chop_val > 50: score += 5
    elif chop_val > 38.2: score += 15
    else: score += 25

    # RSI
    if direction == "LONG":
        if rsi_val < 45: return 0
        elif rsi_val < 55: score += 5
        elif rsi_val < 65: score += 15
        else: score += 20
    else:
        if rsi_val > 55: return 0
        elif rsi_val > 45: score += 5
        elif rsi_val > 35: score += 15
        else: score += 20

    # EMA structure
    if direction == "LONG":
        if ema9 > ema21 > ema50: score += 10
        if ema50 > ema200: score += 5
    else:
        if ema9 < ema21 < ema50: score += 10
        if ema50 < ema200: score += 5

    # ATR
    if atr_now > atr_prev:
        score += 10
    else:
        score += 5

    return min(score, 100)

def position_and_leverage(score):
    if score >= 90: return "5%", "10x"
    if score >= 80: return "4%", "8x"
    if score >= 70: return "3%", "7x"
    return "2%", "5x"

# ================= MAIN LOOP =================
symbols = get_top_usdt_symbols(TOP_COINS)
print(f"🔍 Scanning {len(symbols)} coins...")
send_telegram("🚀 EMA 9–20 Screener Started")

while True:
    now = time.time()

    for symbol in symbols:
        for tf_name, tf_interval in TIMEFRAMES.items():
            try:
                df = fetch_data(symbol, tf_interval)

                ema_fast = ema(df["close"], EMA_FAST)
                ema_slow = ema(df["close"], EMA_SLOW)

                prev_fast, last_fast = ema_fast.iloc[-2], ema_fast.iloc[-1]
                prev_slow, last_slow = ema_slow.iloc[-2], ema_slow.iloc[-1]

                direction = None
                if prev_fast < prev_slow and last_fast > last_slow:
                    direction = "LONG"
                elif prev_fast > prev_slow and last_fast < last_slow:
                    direction = "SHORT"
                else:
                    continue

                candle_time = df["time"].iloc[-1] / 1000
                age = int(now - (candle_time + INTERVAL_SECONDS[tf_name]))
                if age < 0: age = 0
                if age > FRESHNESS_LIMIT: continue

                score = success_rate(direction, df)
                if score < MIN_SUCCESS_RATE: continue

                pos, lev = position_and_leverage(score)

                message = (
                    f"🔥 <b>EMA 9–20 SIGNAL</b>\n\n"
                    f"🪙 <b>Coin:</b> {symbol}\n"
                    f"📊 <b>Direction:</b> {direction}\n"
                    f"⏱ <b>Timeframe:</b> {tf_name}\n"
                    f"🎯 <b>Success Rate:</b> {score}%\n"
                    f"💰 <b>Position Size:</b> {pos}\n"
                    f"⚡ <b>Leverage:</b> {lev}\n"
                    f"🕒 <b>Signal Freshness:</b> {age} sec"
                )

                print(message.replace("<b>", "").replace("</b>", ""))
                send_telegram(message)

            except Exception as e:
                print(f"{symbol} {tf_name} error:", e)

    time.sleep(5)
