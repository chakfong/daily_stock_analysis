# -*- coding: utf-8 -*-
"""Local CYQ (chip distribution) calculator.

Pure-Python implementation of the classic CYQ model.  Works on locally
cached daily K-line data — no external HTTP calls needed.

Reference: 陈浩 CYQ 模型 (Chen Hao CYQ model)
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from data_provider.realtime_types import ChipDistribution

logger = logging.getLogger(__name__)

EPS = 1e-8
_FACTOR = 150  # price grid resolution
_LOOKBACK = 120  # default lookback bars


def calculate_cyq(
    bars: List[Dict[str, Any]],
    index: int = -1,
) -> Optional[ChipDistribution]:
    """Calculate chip distribution from a list of daily bar dicts.

    Each bar must have: date, open, high, low, close, volume, turnover_rate.

    Args:
        bars: list of daily K-line dicts, oldest first
        index: which bar to calculate for (default -1 = latest)

    Returns:
        ChipDistribution or None if insufficient data
    """
    if not bars or len(bars) < 20:
        return None

    # Use last N bars for windowed calculation
    start = max(0, index - _LOOKBACK + 1) if index >= 0 else max(0, len(bars) - _LOOKBACK)
    window = bars[start:index + 1] if index >= 0 else bars[start:]

    if len(window) < 10:
        return None

    # Find price range
    max_price = max(float(b.get("high", 0)) for b in window)
    min_price = min(float(b.get("low", 0)) for b in window)
    if max_price <= 0 or min_price <= 0:
        return None

    accuracy = max(0.01, (max_price - min_price) / (_FACTOR - 1))

    # Build price grid Y-axis
    y_range = [min_price + accuracy * i for i in range(_FACTOR)]

    # Initialize distribution array (横轴 = volume distribution)
    dist = [0.0] * _FACTOR

    for bar in window:
        open_p = float(bar.get("open", 0))
        close_p = float(bar.get("close", 0))
        high_p = float(bar.get("high", 0))
        low_p = float(bar.get("low", 0))
        turnover = float(bar.get("turnover_rate", 0) or 0) / 100.0  # convert % to fraction

        if high_p <= 0 or low_p <= 0 or turnover <= 0:
            # No turnover data → accumulate without decay
            avg_p = (open_p + close_p + high_p + low_p) / 4
            h_idx = min(_FACTOR - 1, max(0, int((high_p - min_price) / accuracy)))
            l_idx = min(_FACTOR - 1, max(0, int((low_p - min_price) / accuracy)))
            g_idx = min(_FACTOR - 1, max(0, int((avg_p - min_price) / accuracy)))

            if high_p == low_p:
                dist[g_idx] += 1.0 / _FACTOR
            else:
                for j in range(min(l_idx, h_idx), max(l_idx, h_idx) + 1):
                    cur_price = min_price + accuracy * j
                    if cur_price <= avg_p:
                        weight = (cur_price - low_p) / (avg_p - low_p) if abs(avg_p - low_p) > EPS else 1.0
                    else:
                        weight = (high_p - cur_price) / (high_p - avg_p) if abs(high_p - avg_p) > EPS else 1.0
                    dist[j] += weight * 1.0 / (abs(h_idx - l_idx) + 1)
            continue

        # Normal bar with turnover → decay old distribution, add new
        decay = 1.0 - turnover
        for i in range(_FACTOR):
            dist[i] *= decay

        avg_p = (open_p + close_p + high_p + low_p) / 4
        h_idx = min(_FACTOR - 1, max(0, int((high_p - min_price) / accuracy)))
        l_idx = min(_FACTOR - 1, max(0, int((low_p - min_price) / accuracy)))

        if high_p == low_p:
            g_idx = min(_FACTOR - 1, max(0, int((avg_p - min_price) / accuracy)))
            dist[g_idx] += turnover / _FACTOR
        else:
            for j in range(min(l_idx, h_idx), max(l_idx, h_idx) + 1):
                cur_price = min_price + accuracy * j
                if cur_price <= avg_p:
                    weight = (cur_price - low_p) / (avg_p - low_p) if abs(avg_p - low_p) > EPS else 1.0
                else:
                    weight = (high_p - cur_price) / (high_p - avg_p) if abs(high_p - avg_p) > EPS else 1.0
                dist[j] += weight * turnover / (abs(h_idx - l_idx) + 1)

    # Normalize distribution
    total = sum(dist)
    if total < EPS:
        return None
    dist = [d / total for d in dist]

    # Current price
    latest = window[-1]
    current_price = float(latest.get("close", 0))

    # Profit ratio: fraction of chips below current price
    current_idx = min(_FACTOR - 1, max(0, int((current_price - min_price) / accuracy)))
    profit_ratio = sum(dist[:current_idx + 1])

    # Weighted average cost
    avg_cost = sum(y_range[i] * dist[i] for i in range(_FACTOR))

    # 90% and 70% concentration
    p90_low, p90_high, p90_conc = _concentration(dist, y_range, 0.90)
    p70_low, p70_high, p70_conc = _concentration(dist, y_range, 0.70)

    bar_date = latest.get("date", "")
    if hasattr(bar_date, "isoformat"):
        bar_date = bar_date.isoformat()

    return ChipDistribution(
        code="",
        date=str(bar_date),
        source="local_cyq",
        profit_ratio=profit_ratio,
        avg_cost=avg_cost,
        cost_90_low=p90_low,
        cost_90_high=p90_high,
        concentration_90=p90_conc,
        cost_70_low=p70_low,
        cost_70_high=p70_high,
        concentration_70=p70_conc,
    )


def _concentration(
    dist: List[float], prices: List[float], pct: float,
) -> Tuple[float, float, float]:
    """Calculate the price range containing *pct* of total chips."""
    cumsum = 0.0
    target_low = (1.0 - pct) / 2.0
    target_high = 1.0 - target_low

    low_idx = high_idx = 0
    for i, d in enumerate(dist):
        cumsum += d
        if cumsum >= target_low and low_idx == 0:
            low_idx = i
        if cumsum >= target_high:
            high_idx = i
            break

    p_low = prices[low_idx] if low_idx < len(prices) else prices[0]
    p_high = prices[high_idx] if high_idx < len(prices) else prices[-1]
    conc = (p_high - p_low) / ((p_high + p_low) / 2) * 100.0 if (p_high + p_low) > EPS else 0.0
    return p_low, p_high, conc


def calculate_cyq_from_db(
    stock_code: str,
    target_date: Optional[date] = None,
) -> Optional[ChipDistribution]:
    """Calculate chip distribution from local DB data.

    If DB doesn't have enough bars, triggers a network fetch via
    history_loader first, then retries.
    """
    from src.services.history_loader import load_history_df
    from src.storage import get_db

    end = target_date or date.today()
    db = get_db()

    # Try DB first
    bars = list(db.get_data_range(stock_code, end - pd.Timedelta(days=365), end) or [])
    if len(bars) < 80:
        # Not enough data — trigger network fetch
        logger.info("CYQ: insufficient DB data for %s, fetching via history_loader", stock_code)
        df, source = load_history_df(stock_code, days=120, target_date=end)
        if df is not None and not df.empty:
            # Re-read from DB after save
            bars = list(db.get_data_range(stock_code, end - pd.Timedelta(days=365), end) or [])

    if not bars:
        return None

    bar_dicts = [b.to_dict() for b in bars]
    result = calculate_cyq(bar_dicts)
    if result:
        result.code = stock_code
    return result
