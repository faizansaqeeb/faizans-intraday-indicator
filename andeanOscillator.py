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

LENGTH = 50
SIGNAL_LENGTH = 9
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

    df[["open","close"]] = df[["open","close"]].astype(float)
    return df

# ================= ANDEAN OSC =================
def andean(df, length=50, signal_length=9):
    alpha = 2 / (length + 1)

    up1 = np.zeros(len(df))
    up2 = np.zeros(len(df))
    dn1 = np.zeros(len(df))
    dn2 = np.zeros(len(df))

    C = df["close"].values
    O = df["open"].values

    for i in range(len(df)):
        if i == 0:
            up1[i] = C[i]
            up2[i] = C[i] ** 2
            dn1[i] = C[i]
            dn2[i] = C[i] ** 2
        else:
            up1[i] = max(C[i], O[i], up1[i-1] - (up1[i-1] - C[i]) * alpha)
            up2[i] = max(C[i]**2, O[i]**2, up2[i-1] - (up2[i-1] - C[i]**2) * alpha)

            dn1[i] = min(C[i], O[i], dn1[i-1] + (C[i] - dn1[i-1]) * alpha)
            dn2[i] = min(C[i]**2, O[i]**2, dn2[i-1] + (C[i]**2 - dn2[i-1]) * alpha)

    bull = np.sqrt(np.maximum(dn2 - dn1 * dn1, 0))
    bear = np.sqrt(np.maximum(up2 - up1 * up1, 0))

    signal = pd.Series(np.maximum(bull, bear)).ewm(
        span=signal_length, adjust=False
    ).mean().values

    return bull, bear, signal

# ================= PLOT =================
fig, axes = plt.subplots(3, 1, figsize=(15, 10))
fig.suptitle("BTCUSDT – Andean Oscillator (Live)", fontsize=14)

def update(frame):
    for ax, (tf_name, tf_interval) in zip(axes, TIMEFRAMES.items()):
        df = fetch_data(tf_interval)

        bull, bear, signal = andean(df)

        ax.clear()

        ax.plot(bull, color="#089981", label="Bull")
        ax.plot(bear, color="#f23645", label="Bear")
        ax.plot(signal, color="#ff9800", label="Signal")

        # Current Trend Label
        trend = "UPTREND (BUY BIAS)" if bull[-1] > bear[-1] else "DOWNTREND (SELL BIAS)"
        color = "green" if bull[-1] > bear[-1] else "red"

        ax.set_title(f"{tf_name} | {trend}", color=color)
        ax.legend(loc="upper right")
        ax.grid(alpha=0.3)

ani = FuncAnimation(fig, update, interval=UPDATE_INTERVAL_MS)
plt.tight_layout()
plt.show()
