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

ADX_LEN = 14
DI_LEN = 14
CANDLE_LIMIT = 200
UPDATE_INTERVAL_MS = 5000

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

    df[["high","low","close"]] = df[["high","low","close"]].astype(float)
    return df

# ================= RMA (TradingView ta.rma) =================
def rma(series, length):
    rma_vals = np.zeros(len(series))
    rma_vals[0] = series[0]
    alpha = 1 / length

    for i in range(1, len(series)):
        rma_vals[i] = alpha * series[i] + (1 - alpha) * rma_vals[i-1]

    return rma_vals

# ================= ADX (TV ACCURATE) =================
def adx_tv(df, di_len=14, adx_len=14):
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values

    up = np.diff(high, prepend=high[0])
    down = -np.diff(low, prepend=low[0])

    plusDM = np.where((up > down) & (up > 0), up, 0)
    minusDM = np.where((down > up) & (down > 0), down, 0)

    tr = np.maximum.reduce([
        high - low,
        np.abs(high - np.roll(close, 1)),
        np.abs(low - np.roll(close, 1))
    ])
    tr[0] = high[0] - low[0]

    tr_rma = rma(tr, di_len)

    plusDI = 100 * rma(plusDM, di_len) / tr_rma
    minusDI = 100 * rma(minusDM, di_len) / tr_rma

    plusDI = np.nan_to_num(plusDI)
    minusDI = np.nan_to_num(minusDI)

    sum_di = plusDI + minusDI
    dx = 100 * np.abs(plusDI - minusDI) / np.where(sum_di == 0, 1, sum_di)

    adx = rma(dx, adx_len)
    return adx

# ================= PLOT =================
fig, axes = plt.subplots(3, 1, figsize=(15, 10))
fig.suptitle("BTCUSDT – ADX (TradingView Accurate)", fontsize=14)

def update(frame):
    for ax, (tf_name, tf_interval) in zip(axes, TIMEFRAMES.items()):
        df = fetch_data(tf_interval)
        adx = adx_tv(df)

        ax.clear()

        # ADX Line
        ax.plot(adx, color="yellow", linewidth=2, label="ADX")

        # Horizontal 25 line
        ax.axhline(25, color="blue", linestyle="--", linewidth=1)

        # Current ADX value
        current_adx = adx[-1]
        ax.text(
            0.98, 0.9,
            f"ADX: {current_adx:.2f}",
            transform=ax.transAxes,
            ha="right",
            color="yellow",
            fontsize=11,
            bbox=dict(facecolor="black", alpha=0.6)
        )

        ax.set_ylim(0, max(50, np.nanmax(adx) + 5))
        ax.set_title(f"{tf_name} | ADX", color="white")
        ax.grid(alpha=0.3)
        ax.legend(loc="upper left")

ani = FuncAnimation(fig, update, interval=UPDATE_INTERVAL_MS)
plt.tight_layout()
plt.show()