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

LENGTH = 14
CANDLE_LIMIT = 210              # little extra buffer
UPDATE_INTERVAL_MS = 5000       # 5 seconds

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

    df[["open","high","low","close"]] = df[["open","high","low","close"]].astype(float)
    return df

# ================= ATR(1) — TradingView Accurate =================
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

# ================= CHOPPINESS INDEX =================
def choppiness_index(df, length=14):
    atr = atr_1(df)
    atr_sum = atr.rolling(length).sum()

    highest_high = df["high"].rolling(length).max()
    lowest_low = df["low"].rolling(length).min()

    ci = 100 * np.log10(atr_sum / (highest_high - lowest_low)) / np.log10(length)
    return ci

# ================= PLOT =================
fig, axes = plt.subplots(3, 1, figsize=(16, 10))
fig.suptitle("BTCUSDT – Choppiness Index (TradingView Matched)", fontsize=14)

def update(frame):
    for ax, (tf_name, tf_interval) in zip(axes, TIMEFRAMES.items()):
        # 🔒 DROP LIVE CANDLE (matches TradingView wait-for-close)
        df = fetch_data(tf_interval).iloc[:-1]

        ci = choppiness_index(df)

        ax.clear()

        # CHOP plot
        ax.plot(ci, color="#2962FF", linewidth=1.6, label="CHOP")

        # Fixed TradingView Bands
        ax.axhline(61.8, linestyle="--", color="#787B86")
        ax.axhline(50, linestyle="--", color="#AAAAAA")
        ax.axhline(38.2, linestyle="--", color="#787B86")

        ax.fill_between(
            range(len(ci)),
            61.8,
            38.2,
            color=(33/255, 150/255, 243/255, 0.30)
        )

        # ================= DYNAMIC VALUE CARD =================
        last_ci = ci.dropna().iloc[-1]

        if last_ci > 61.8:
            state = "CHOPPY"
            card_color = "#f39c12"
        elif last_ci < 38.2:
            state = "TRENDING"
            card_color = "#2ecc71"
        else:
            state = "TRANSITION"
            card_color = "#7f8c8d"

        ax.text(
            0.99, 0.90,
            f"CHOP: {last_ci:.2f}\n{state}",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=11,
            fontweight="bold",
            color="white",
            bbox=dict(
                boxstyle="round,pad=0.4",
                facecolor=card_color,
                edgecolor="none",
                alpha=0.95
            )
        )

        ax.set_title(f"{tf_name} Timeframe", fontsize=11)
        ax.set_ylim(0, 100)
        ax.grid(alpha=0.3)
        ax.legend(loc="upper left")

ani = FuncAnimation(fig, update, interval=UPDATE_INTERVAL_MS)
plt.tight_layout()
plt.show()