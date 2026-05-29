from __future__ import annotations

import pandas as pd

from stocknoti.models import TechnicalSnapshot


def _last_number(series: pd.Series) -> float | None:
    clean = series.dropna()
    if clean.empty:
        return None
    return float(clean.iloc[-1])


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def support_resistance(history: pd.DataFrame, window: int = 60) -> tuple[float | None, float | None]:
    if history.empty or "Low" not in history or "High" not in history:
        return None, None

    recent = history.tail(window)
    support = _last_number(recent["Low"].rolling(10).min())
    resistance = _last_number(recent["High"].rolling(10).max())
    return support, resistance


def build_technical_snapshot(history: pd.DataFrame) -> TechnicalSnapshot:
    if history.empty or "Close" not in history:
        return TechnicalSnapshot("ไม่มีข้อมูล", 0, None, None, None, None, None, None, None, None, None)

    close = history["Close"].dropna()
    volume = history["Volume"].dropna() if "Volume" in history else pd.Series(dtype=float)
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()
    rsi14 = compute_rsi(close)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    macd_signal = macd_line.ewm(span=9, adjust=False).mean()
    support, resistance = support_resistance(history)

    last_close = float(close.iloc[-1])
    last_sma20 = _last_number(sma20)
    last_sma50 = _last_number(sma50)
    last_sma200 = _last_number(sma200)
    last_rsi = _last_number(rsi14)
    last_macd = _last_number(macd_line)
    last_signal = _last_number(macd_signal)

    volume_ratio = None
    if len(volume) >= 20:
        avg_volume = volume.tail(20).mean()
        if avg_volume:
            volume_ratio = float(volume.iloc[-1] / avg_volume)

    if last_sma20 and last_sma50 and last_close > last_sma20 > last_sma50:
        trend = "ขาขึ้นระยะสั้น"
    elif last_sma50 and last_sma200 and last_close > last_sma50 > last_sma200:
        trend = "ขาขึ้นระยะกลาง"
    elif last_sma20 and last_sma50 and last_close < last_sma20 < last_sma50:
        trend = "ขาลง"
    else:
        trend = "แกว่งตัว/รอสัญญาณ"

    return TechnicalSnapshot(
        trend=trend,
        close=last_close,
        sma20=last_sma20,
        sma50=last_sma50,
        sma200=last_sma200,
        rsi14=last_rsi,
        macd=last_macd,
        macd_signal=last_signal,
        support=support,
        resistance=resistance,
        volume_ratio=volume_ratio,
    )
