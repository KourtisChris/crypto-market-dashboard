# ============================================================
# backend/engine/signals.py
# 7 market states with composite score-based selection.
# When multiple states are active simultaneously, the one
# with the highest normalized composite score wins.
# ============================================================

from dataclasses import dataclass, field

from config import THRESHOLDS, LATE_ALTS_BTCD_LEVEL
from feeds.binance import get_pct_change, get_altbtc_pct
from feeds.coingecko import get_global_pct_change


# ----------------------------------------------------------
# Data containers
# ----------------------------------------------------------
@dataclass
class Metrics:
    btc_chg:    float   # BTC % change from candle open
    btcd_chg:   float   # BTC.D % change from candle open
    total2_chg: float   # TOTAL2 % change
    total3_chg: float   # TOTAL3 % change
    ethbtc_chg: float   # ETH/BTC % change
    btcd_level: float   # current BTC.D absolute value


@dataclass
class StateResult:
    label:  str
    type:   str    # "long" | "short" | "neutral" | "caution" | "risk_off"
    score:  float  # composite normalized score (higher = stronger signal)
    emoji:  str


@dataclass
class CoinScore:
    symbol:        str
    rank:          int
    altbtc_chg:    float
    vs_total2:     float
    score:         float
    hidden_signal: str = ""   # "hidden_strength" | "hidden_weakness" | ""


# ----------------------------------------------------------
# State definitions
# Each state has:
#   - check(m, thr) → bool: are conditions met?
#   - score(m, thr) → float: normalized composite strength
# ----------------------------------------------------------

class _State:
    label: str
    type:  str
    emoji: str

    @classmethod
    def check(cls, m: Metrics, thr: dict) -> bool:
        raise NotImplementedError

    @classmethod
    def score(cls, m: Metrics, thr: dict) -> float:
        raise NotImplementedError


class BTCLong(_State):
    label = "BTC Long"
    type  = "long"
    emoji = "🟠"

    @classmethod
    def check(cls, m: Metrics, thr: dict) -> bool:
        return m.btc_chg > thr["btc"] and m.btcd_chg > thr["btcd"]

    @classmethod
    def score(cls, m: Metrics, thr: dict) -> float:
        # Both BTC and BTC.D must be rising — score = average of normalized moves
        return (m.btc_chg / thr["btc"] + m.btcd_chg / thr["btcd"]) / 2


class AltsLong(_State):
    label = "Alts Long"
    type  = "long"
    emoji = "🟢"

    @classmethod
    def check(cls, m: Metrics, thr: dict) -> bool:
        btc_flat_or_up = m.btc_chg > -thr["btc"]
        btcd_falling   = m.btcd_chg < -thr["btcd"]
        t2_rising      = m.total2_chg > thr["total2"]
        return btc_flat_or_up and btcd_falling and t2_rising

    @classmethod
    def score(cls, m: Metrics, thr: dict) -> float:
        return (abs(m.btcd_chg) / thr["btcd"] + m.total2_chg / thr["total2"]) / 2


class ETHLeading(_State):
    label = "ETH Leading"
    type  = "long"
    emoji = "🔵"

    @classmethod
    def check(cls, m: Metrics, thr: dict) -> bool:
        return m.btcd_chg < -thr["btcd"] and m.ethbtc_chg > thr["ethbtc"]

    @classmethod
    def score(cls, m: Metrics, thr: dict) -> float:
        return (abs(m.btcd_chg) / thr["btcd"] + m.ethbtc_chg / thr["ethbtc"]) / 2


class LateAlts(_State):
    label = "Late Alts"
    type  = "caution"
    emoji = "🟡"

    @classmethod
    def check(cls, m: Metrics, thr: dict) -> bool:
        return m.btcd_level < LATE_ALTS_BTCD_LEVEL and m.total2_chg > thr["total2"]

    @classmethod
    def score(cls, m: Metrics, thr: dict) -> float:
        # Score based on how far below the threshold BTC.D is + TOTAL2 strength
        btcd_distance = (LATE_ALTS_BTCD_LEVEL - m.btcd_level) / LATE_ALTS_BTCD_LEVEL * 100
        return (btcd_distance + m.total2_chg / thr["total2"]) / 2


class AltsShort(_State):
    label = "Alts Short"
    type  = "short"
    emoji = "🔴"

    @classmethod
    def check(cls, m: Metrics, thr: dict) -> bool:
        return m.btc_chg < -thr["btc"] and m.btcd_chg > thr["btcd"]

    @classmethod
    def score(cls, m: Metrics, thr: dict) -> float:
        return (abs(m.btc_chg) / thr["btc"] + m.btcd_chg / thr["btcd"]) / 2


class RiskOff(_State):
    label = "Risk Off"
    type  = "risk_off"
    emoji = "⚫"

    @classmethod
    def check(cls, m: Metrics, thr: dict) -> bool:
        # Everything falls together — including BTC.D (capital exits crypto entirely)
        return (m.btc_chg < -thr["btc"]
                and m.total2_chg < -thr["total2"]
                and m.btcd_chg < thr["btcd"])   # BTC.D not rising = no BTC refuge

    @classmethod
    def score(cls, m: Metrics, thr: dict) -> float:
        return (abs(m.btc_chg) / thr["btc"] + abs(m.total2_chg) / thr["total2"]) / 2


class Neutral(_State):
    label = "Neutral"
    type  = "neutral"
    emoji = "⚪"

    @classmethod
    def check(cls, m: Metrics, thr: dict) -> bool:
        return True   # always active as default

    @classmethod
    def score(cls, m: Metrics, thr: dict) -> float:
        return 0.0


# All states ordered — Neutral is always last (default fallback)
ALL_STATES = [BTCLong, AltsLong, ETHLeading, LateAlts, AltsShort, RiskOff, Neutral]


# ----------------------------------------------------------
# Core: build metrics + determine winning state
# ----------------------------------------------------------
def build_metrics(tf: str, state: dict) -> Metrics | None:
    prices = state.get("prices", {})
    glb    = state.get("global", {})
    if not prices or not glb:
        return None

    btc_chg    = get_pct_change("BTCUSDT", tf, prices)
    ethbtc_chg = get_pct_change("ETHBTC",  tf, prices)
    if btc_chg is None or ethbtc_chg is None:
        return None

    btcd_now   = glb.get("btcd",   0)
    total2_now = glb.get("total2", 0)
    total3_now = glb.get("total3", 0)

    return Metrics(
        btc_chg    = btc_chg,
        btcd_chg   = get_global_pct_change("btcd",   tf, btcd_now),
        total2_chg = get_global_pct_change("total2", tf, total2_now),
        total3_chg = get_global_pct_change("total3", tf, total3_now),
        ethbtc_chg = ethbtc_chg,
        btcd_level = btcd_now,
    )


def get_market_state(m: Metrics, tf: str) -> StateResult:
    """
    Evaluates all states, collects those whose conditions are met,
    and returns the one with the highest composite score.
    Neutral is always included as a fallback with score 0.
    """
    thr = THRESHOLDS[tf]
    candidates = []

    for state_cls in ALL_STATES:
        if state_cls.check(m, thr):
            s = state_cls.score(m, thr)
            candidates.append((s, state_cls))

    # Pick the highest scoring candidate
    candidates.sort(key=lambda x: x[0], reverse=True)
    score, winner = candidates[0]

    return StateResult(
        label  = winner.label,
        type   = winner.type,
        score  = round(score, 4),
        emoji  = winner.emoji,
    )


# ----------------------------------------------------------
# Per-coin scoring (for top movers section)
# ----------------------------------------------------------
def score_coins(tf: str, state: dict) -> list[CoinScore]:
    top100     = state.get("top100", [])
    prices     = state.get("prices", {})
    glb        = state.get("global", {})
    total2_now = glb.get("total2", 0)
    t2_chg     = get_global_pct_change("total2", tf, total2_now) if total2_now else 0.0
    btc_chg    = get_pct_change("BTCUSDT", tf, prices) or 0.0

    scored = []
    for coin in top100:
        sym = coin["symbol"]
        if sym in ("BTC", "ETH"):
            continue
        altbtc_chg = (get_pct_change(f"{sym}BTC", tf, prices)
                      if coin["direct_btc"]
                      else get_altbtc_pct(sym, tf, prices))
        if altbtc_chg is None:
            continue
        alt_usdt_chg = get_pct_change(f"{sym}USDT", tf, prices)
        if alt_usdt_chg is None:
            continue

        vs_total2 = alt_usdt_chg - t2_chg

        hidden = ""
        if btc_chg > 0 and altbtc_chg < 0:
            hidden = "hidden_weakness"
        elif btc_chg < 0 and altbtc_chg > 0:
            hidden = "hidden_strength"

        score = altbtc_chg + vs_total2
        if hidden == "hidden_weakness":
            score -= abs(altbtc_chg) * 0.5
        elif hidden == "hidden_strength":
            score += abs(altbtc_chg) * 0.5

        scored.append(CoinScore(
            symbol        = f"{sym}USDT",
            rank          = coin["rank"],
            altbtc_chg    = altbtc_chg,
            vs_total2     = vs_total2,
            score         = score,
            hidden_signal = hidden,
        ))

    return scored


def get_top_strong(scores: list[CoinScore], n: int = 5) -> list[CoinScore]:
    return sorted(scores, key=lambda x: x.score, reverse=True)[:n]


def get_top_weak(scores: list[CoinScore], n: int = 5) -> list[CoinScore]:
    return sorted(scores, key=lambda x: x.score)[:n]
