from binance.client import Client
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# ================= CONFIG =================
SYMBOL = "BTCUSDT"
TIMEFRAMES = {
    "5m": Client.KLINE_INTERVAL_5MINUTE,
    "15m": Client.KLINE_INTERVAL_15MINUTE,
    "1h": Client.KLINE_INTERVAL_1HOUR
}

EMA_FAST = 9
EMA_SLOW = 20
CANDLE_LIMIT = 200
UPDATE_INTERVAL_MS = 5000  # 5 seconds

client = Client()

# ================= DATA =================
def fetch_data(interval):
    klines = client.futures_klines(
        symbol=SYMBOL,
        interval=interval,
        limit=CANDLE_LIMIT
    )

    df = pd.DataFrame(klines, columns=[
        "time","open","high","low","close","volume",
        "c1","c2","c3","c4","c5","c6"
    ])

    df["close"] = df["close"].astype(float)
    df["time"] = pd.to_datetime(df["time"], unit="ms")
    return df

# ================= EMA STRATEGY =================
def ema_strategy(df):
    df["ema_fast"] = df["close"].ewm(span=EMA_FAST, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=EMA_SLOW, adjust=False).mean()

    df["long_signal"] = (
        (df["ema_fast"] > df["ema_slow"]) &
        (df["ema_fast"].shift(1) <= df["ema_slow"].shift(1))
    )

    df["short_signal"] = (
        (df["ema_fast"] < df["ema_slow"]) &
        (df["ema_fast"].shift(1) >= df["ema_slow"].shift(1))
    )

    return df

# ================= PLOT =================
fig, axes = plt.subplots(3, 1, figsize=(16, 10), sharex=False)
fig.suptitle("BTCUSDT – EMA 9 / EMA 20 Crossover Strategy (Live)", fontsize=14)

def update(frame):
    for ax, (tf_name, tf_interval) in zip(axes, TIMEFRAMES.items()):
        df = fetch_data(tf_interval)
        df = ema_strategy(df)

        ax.clear()

        # Price (faded)
        ax.plot(df["close"], color="gray", alpha=0.3)

        # EMA Lines
        ax.plot(df["ema_fast"], color="blue", linewidth=2, label="EMA 9")
        ax.plot(df["ema_slow"], color="red", linewidth=2, label="EMA 20")

        # LONG signals
        ax.scatter(
            df.index[df["long_signal"]],
            df["ema_fast"][df["long_signal"]],
            marker="^",
            color="green",
            s=120,
            label="LONG"
        )

        # SHORT signals
        ax.scatter(
            df.index[df["short_signal"]],
            df["ema_fast"][df["short_signal"]],
            marker="v",
            color="red",
            s=120,
            label="SHORT"
        )

        # Trend label
        trend = "UPTREND (BUY)" if df["ema_fast"].iloc[-1] > df["ema_slow"].iloc[-1] else "DOWNTREND (SELL)"
        trend_color = "green" if trend.startswith("UP") else "red"

        ax.set_title(f"{tf_name} | {trend}", color=trend_color)
        ax.legend(loc="upper left")
        ax.grid(alpha=0.3)

ani = FuncAnimation(fig, update, interval=UPDATE_INTERVAL_MS)
plt.tight_layout()
plt.show()