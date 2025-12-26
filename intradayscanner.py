from binance.client import Client
import pandas as pd
import ta
import requests
from datetime import datetime

# ================= TELEGRAM CONFIG =================
BOT_TOKEN = "8565575662:AAGkqeUhSI0qXzXBFDdzIgEzR4gzm2iohAw"
CHAT_ID = "2137177601"

# ================= BINANCE FUTURES CLIENT =================
client = Client()

# ================= TELEGRAM FUNCTION =================
def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, data=payload)

# ================= GET TOP 500 FUTURES SYMBOLS BY VOLUME =================
def get_top_futures_symbols(limit=500):
    tickers = client.futures_ticker()
    usdt_pairs = [t for t in tickers if t['symbol'].endswith('USDT')]
    sorted_pairs = sorted(
        usdt_pairs,
        key=lambda x: float(x['quoteVolume']),
        reverse=True
    )
    return [p['symbol'] for p in sorted_pairs[:limit]]

# ================= EMA CHECK FUNCTION (MULTI TF) =================
def check_ema(symbol, interval, tf_name):
    try:
        klines = client.futures_klines(
            symbol=symbol,
            interval=interval,
            limit=100
        )

        df = pd.DataFrame(klines, columns=[
            'time','open','high','low','close','volume',
            'c1','c2','c3','c4','c5','c6'
        ])

        df['close'] = df['close'].astype(float)

        df['ema9'] = ta.trend.EMAIndicator(df['close'], 9).ema_indicator()
        df['ema20'] = ta.trend.EMAIndicator(df['close'], 20).ema_indicator()

        prev = df.iloc[-2]
        curr = df.iloc[-1]

        bias = "BULLISH" if curr.ema9 > curr.ema20 else "BEARISH"

        # ===== BULLISH CROSS =====
        if prev.ema9 < prev.ema20 and curr.ema9 > curr.ema20:
            send_telegram(
                f"🟢 EMA 9/20 BULLISH CROSS\n\n"
                f"Coin: {symbol}\n"
                f"TF: {tf_name}\n"
                f"Bias: {bias}\n"
                f"Type: Futures\n"
                f"Time: {datetime.utcnow()} UTC"
            )

        # ===== BEARISH CROSS =====
        elif prev.ema9 > prev.ema20 and curr.ema9 < curr.ema20:
            send_telegram(
                f"🔴 EMA 9/20 BEARISH CROSS\n\n"
                f"Coin: {symbol}\n"
                f"TF: {tf_name}\n"
                f"Bias: {bias}\n"
                f"Type: Futures\n"
                f"Time: {datetime.utcnow()} UTC"
            )

    except Exception as e:
        print(f"{symbol} {tf_name} error: {e}")

# ================= RUN SCANNER =================
def run_once():
    symbols = get_top_futures_symbols(500)

    send_telegram(
        "✅ Futures EMA Intraday Scalp Scanner Started\n"
        "TFs: 5m | 15m\n"
        "EMA: 9 / 20\n"
        "Top 500 by Volume"
    )

    for sym in symbols:
        # 5 MIN
        check_ema(sym, Client.KLINE_INTERVAL_5MINUTE, "5m")

        # 15 MIN
        check_ema(sym, Client.KLINE_INTERVAL_15MINUTE, "15m")

# ================= START =================
run_once()
