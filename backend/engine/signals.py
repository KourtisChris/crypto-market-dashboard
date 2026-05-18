# ============================================================
# backend/engine/signals.py
# 7 market states with primary + confirmation scoring.
#
# Activation rule:
#   ALL primary criteria must be met
#   AND at least 1 confirmation criterion must be met
#
# Score = hits / total_criteria (ratio 0.0–1.0)
# Confidence: High >= 0.75, Medium >= 0.50, Low >= 0.28
#
# Conflict resolution (when multiple signals qualify):
#   1. Highest score wins
#   2. Tie: most primary hits
#   3. Tie: priority order (Risk Off > Alts Short > BTC Long > ...)
# ============================================================

from dataclasses import dataclass
from config import (
    THRESHOLDS, LATE_ALTS_BTCD_LEVEL, SIGNAL_PRIORITY,
    FUNDING_DEEPLY_NEGATIVE, FUNDING_NEGATIVE,
    FUNDING_NEUTRAL_MIN, FUNDING_NEUTRAL_MAX, FUNDING_HIGH_POSITIVE,
    FEAR_GREED_EXTREME_FEAR, FEAR_GREED_FEAR,
    FEAR_GREED_NEUTRAL_MAX, FEAR_GREED_GREED_MAX,
    STABLE_D_SHARPLY_RISING, STABLE_D_RISING, STABLE_D_FALLING,
    VOLUME_ABOVE_AVG_RATIO, VOLUME_BELOW_AVG_RATIO,
)
from feeds.binance import get_pct_change, get_altbtc_pct
from feeds.coingecko import get_global_pct_change, get_stable_d_change, get_fear_greed


# ----------------------------------------------------------
# Data containers
# ----------------------------------------------------------
@dataclass
class Metrics:
    btc_chg:    float
    btcd_chg:   float
    total2_chg: float
    total3_chg: float
    ethbtc_chg: float
    btcd_level: float


@dataclass
class ConfirmationData:
    """Evaluated confirmation criteria values."""
    btc_volume_ratio:   float | None   # current / 30d avg
    alt_volume_ratio:   float | None
    total_volume_ratio: float | None
    funding_rate:       float | None
    fear_greed_value:   int | None
    stable_d_change:    float | None   # pp change over ~1h
    # stale flags
    volume_stale:       bool = True
    funding_stale:      bool = True
    fear_greed_stale:   bool = True


@dataclass
class SignalScore:
    label:         str
    type:          str
    emoji:         str
    hits:          int
    total:         int
    score:         float    # hits / total
    confidence:    str      # "High" | "Medium" | "Low" | "None"
    primary_hits:  int
    primary_total: int
    active:        bool     # True if qualifies (all primary met + >=1 confirmation)


@dataclass
class StateResult:
    label:         str
    type:          str
    score:         float    # legacy composite score for heatmap/history
    emoji:         str
    hits:          int
    total:         int
    confidence:    str
    primary_hits:  int
    primary_total: int
    all_scores:    list     # list of SignalScore for all signals


@dataclass
class CoinScore:
    symbol:        str
    rank:          int
    altbtc_chg:    float
    vs_total2:     float
    score:         float
    hidden_signal: str = ""


# ----------------------------------------------------------
# Confidence label
# ----------------------------------------------------------
def _confidence_label(score: float) -> str:
    if score >= 0.75:
        return "High"
    if score >= 0.50:
        return "Medium"
    if score >= 0.28:
        return "Low"
    return "None"


# ----------------------------------------------------------
# Confirmation helpers
# ----------------------------------------------------------
def _volume_above_avg(ratio: float | None) -> bool:
    if ratio is None:
        return False
    return ratio >= VOLUME_ABOVE_AVG_RATIO

def _volume_falling(ratio: float | None) -> bool:
    if ratio is None:
        return False
    return ratio < VOLUME_BELOW_AVG_RATIO

def _funding_neutral_or_negative(rate: float | None) -> bool:
    if rate is None:
        return False
    return rate <= FUNDING_NEUTRAL_MAX

def _funding_deeply_negative(rate: float | None) -> bool:
    if rate is None:
        return False
    return rate < FUNDING_DEEPLY_NEGATIVE

def _funding_high_positive(rate: float | None) -> bool:
    if rate is None:
        return False
    return rate > FUNDING_HIGH_POSITIVE

def _fg_fear(val: int | None) -> bool:
    if val is None:
        return False
    return val < FEAR_GREED_FEAR

def _fg_extreme_fear(val: int | None) -> bool:
    if val is None:
        return False
    return val < FEAR_GREED_EXTREME_FEAR

def _fg_neutral_to_greed(val: int | None) -> bool:
    if val is None:
        return False
    return FEAR_GREED_FEAR <= val < FEAR_GREED_GREED_MAX

def _fg_mid_greed(val: int | None) -> bool:
    if val is None:
        return False
    return FEAR_GREED_NEUTRAL_MAX <= val < FEAR_GREED_GREED_MAX

def _fg_extreme_greed(val: int | None) -> bool:
    if val is None:
        return False
    return val >= FEAR_GREED_GREED_MAX

def _stable_d_falling(change: float | None) -> bool:
    if change is None:
        return False
    return change < STABLE_D_FALLING

def _stable_d_rising(change: float | None) -> bool:
    if change is None:
        return False
    return change > STABLE_D_RISING

def _stable_d_sharply_rising(change: float | None) -> bool:
    if change is None:
        return False
    return change > STABLE_D_SHARPLY_RISING


# ----------------------------------------------------------
# Signal definitions
# Each has: primary_check, confirmations list
# ----------------------------------------------------------

def _eval_btc_long(m: Metrics, thr: dict, c: ConfirmationData) -> SignalScore:
    # Primary (all must be True)
    p1 = m.btc_chg  > thr["btc"]
    p2 = m.btcd_chg > thr["btcd"]
    primaries = [p1, p2]
    primary_hits = sum(primaries)

    # Confirmation (at least 1 must be True)
    cf1 = _volume_above_avg(c.btc_volume_ratio)
    cf2 = _funding_neutral_or_negative(c.funding_rate)
    cf3 = _fg_fear(c.fear_greed_value)
    cf4 = _stable_d_falling(c.stable_d_change)
    confirmations = [cf1, cf2, cf3, cf4]
    conf_hits = sum(confirmations)

    hits  = primary_hits + conf_hits
    total = len(primaries) + len(confirmations)
    score = hits / total
    active = all(primaries) and conf_hits >= 1

    return SignalScore(
        label="BTC Long", type="long", emoji="🟠",
        hits=hits, total=total, score=round(score, 3),
        confidence=_confidence_label(score) if active else "None",
        primary_hits=primary_hits, primary_total=len(primaries),
        active=active,
    )


def _eval_alts_long(m: Metrics, thr: dict, c: ConfirmationData) -> SignalScore:
    p1 = m.btc_chg    > -thr["btc"]
    p2 = m.btcd_chg   < -thr["btcd"]
    p3 = m.total2_chg > thr["total2"]
    primaries = [p1, p2, p3]
    primary_hits = sum(primaries)

    cf1 = _volume_above_avg(c.alt_volume_ratio)
    cf2 = _funding_neutral_or_negative(c.funding_rate)
    cf3 = _fg_neutral_to_greed(c.fear_greed_value)
    cf4 = _stable_d_falling(c.stable_d_change)
    confirmations = [cf1, cf2, cf3, cf4]
    conf_hits = sum(confirmations)

    hits  = primary_hits + conf_hits
    total = len(primaries) + len(confirmations)
    score = hits / total
    active = all(primaries) and conf_hits >= 1

    return SignalScore(
        label="Alts Long", type="long", emoji="🟢",
        hits=hits, total=total, score=round(score, 3),
        confidence=_confidence_label(score) if active else "None",
        primary_hits=primary_hits, primary_total=len(primaries),
        active=active,
    )


def _eval_eth_leading(m: Metrics, thr: dict, c: ConfirmationData) -> SignalScore:
    p1 = m.btcd_chg   < -thr["btcd"]
    p2 = m.ethbtc_chg > thr["ethbtc"]
    primaries = [p1, p2]
    primary_hits = sum(primaries)

    cf1 = _funding_neutral_or_negative(c.funding_rate)
    cf2 = _fg_mid_greed(c.fear_greed_value)
    cf3 = _stable_d_falling(c.stable_d_change)
    confirmations = [cf1, cf2, cf3]
    conf_hits = sum(confirmations)

    hits  = primary_hits + conf_hits
    total = len(primaries) + len(confirmations)
    score = hits / total
    active = all(primaries) and conf_hits >= 1

    return SignalScore(
        label="ETH Leading", type="long", emoji="🔵",
        hits=hits, total=total, score=round(score, 3),
        confidence=_confidence_label(score) if active else "None",
        primary_hits=primary_hits, primary_total=len(primaries),
        active=active,
    )


def _eval_late_alts(m: Metrics, thr: dict, c: ConfirmationData) -> SignalScore:
    p1 = m.btcd_level  < LATE_ALTS_BTCD_LEVEL
    p2 = m.total2_chg  > thr["total2"]
    primaries = [p1, p2]
    primary_hits = sum(primaries)

    cf1 = _volume_above_avg(c.total_volume_ratio)
    cf2 = _funding_high_positive(c.funding_rate)
    cf3 = _fg_extreme_greed(c.fear_greed_value)
    cf4 = _stable_d_falling(c.stable_d_change)
    confirmations = [cf1, cf2, cf3, cf4]
    conf_hits = sum(confirmations)

    hits  = primary_hits + conf_hits
    total = len(primaries) + len(confirmations)
    score = hits / total
    active = all(primaries) and conf_hits >= 1

    return SignalScore(
        label="Late Alts", type="caution", emoji="🟡",
        hits=hits, total=total, score=round(score, 3),
        confidence=_confidence_label(score) if active else "None",
        primary_hits=primary_hits, primary_total=len(primaries),
        active=active,
    )


def _eval_alts_short(m: Metrics, thr: dict, c: ConfirmationData) -> SignalScore:
    p1 = m.btc_chg  < -thr["btc"]
    p2 = m.btcd_chg > thr["btcd"]
    primaries = [p1, p2]
    primary_hits = sum(primaries)

    cf1 = _volume_falling(c.alt_volume_ratio)
    cf2 = _funding_neutral_or_negative(c.funding_rate)
    cf3 = _fg_fear(c.fear_greed_value)
    cf4 = _stable_d_rising(c.stable_d_change)
    confirmations = [cf1, cf2, cf3, cf4]
    conf_hits = sum(confirmations)

    hits  = primary_hits + conf_hits
    total = len(primaries) + len(confirmations)
    score = hits / total
    active = all(primaries) and conf_hits >= 1

    return SignalScore(
        label="Alts Short", type="short", emoji="🔴",
        hits=hits, total=total, score=round(score, 3),
        confidence=_confidence_label(score) if active else "None",
        primary_hits=primary_hits, primary_total=len(primaries),
        active=active,
    )


def _eval_risk_off(m: Metrics, thr: dict, c: ConfirmationData) -> SignalScore:
    p1 = m.btc_chg    < -thr["btc"]
    p2 = m.btcd_chg   < thr["btcd"]    # NOT rising
    p3 = m.total2_chg < -thr["total2"]
    primaries = [p1, p2, p3]
    primary_hits = sum(primaries)

    cf1 = _volume_falling(c.total_volume_ratio)
    cf2 = _funding_deeply_negative(c.funding_rate)
    cf3 = _fg_extreme_fear(c.fear_greed_value)
    cf4 = _stable_d_sharply_rising(c.stable_d_change)
    confirmations = [cf1, cf2, cf3, cf4]
    conf_hits = sum(confirmations)

    hits  = primary_hits + conf_hits
    total = len(primaries) + len(confirmations)
    score = hits / total
    active = all(primaries) and conf_hits >= 1

    return SignalScore(
        label="Risk Off", type="risk_off", emoji="⚫",
        hits=hits, total=total, score=round(score, 3),
        confidence=_confidence_label(score) if active else "None",
        primary_hits=primary_hits, primary_total=len(primaries),
        active=active,
    )


ALL_EVALUATORS = [
    _eval_btc_long,
    _eval_alts_long,
    _eval_eth_leading,
    _eval_late_alts,
    _eval_alts_short,
    _eval_risk_off,
]


# ----------------------------------------------------------
# Build confirmation data from state
# ----------------------------------------------------------
def build_confirmation_data(state: dict) -> ConfirmationData:
    from feeds.binance import get_volume_data, get_funding_data

    vol     = state.get("volume", get_volume_data())
    fund    = state.get("funding", get_funding_data())
    fg      = state.get("fear_greed", get_fear_greed())
    vol_avg = state.get("volume_avg", {})

    # Volume ratios
    btc_ratio   = None
    alt_ratio   = None
    total_ratio = None

    btc_avg   = vol_avg.get("btc_24h")
    alt_avg   = vol_avg.get("alt_24h")
    total_avg = vol_avg.get("total_24h")

    if btc_avg and btc_avg > 0 and not vol.get("stale"):
        btc_ratio = vol["btc_24h"] / btc_avg
    if alt_avg and alt_avg > 0 and not vol.get("stale"):
        alt_ratio = vol["alt_24h"] / alt_avg
    if total_avg and total_avg > 0 and not vol.get("stale"):
        total_ratio = vol["total_24h"] / total_avg

    funding_rate = fund.get("rate") if not fund.get("stale") else None
    fg_value     = fg.get("value")  if not fg.get("stale")   else None
    stable_chg   = get_stable_d_change()

    return ConfirmationData(
        btc_volume_ratio=btc_ratio,
        alt_volume_ratio=alt_ratio,
        total_volume_ratio=total_ratio,
        funding_rate=funding_rate,
        fear_greed_value=fg_value,
        stable_d_change=stable_chg,
        volume_stale=vol.get("stale", True),
        funding_stale=fund.get("stale", True),
        fear_greed_stale=fg.get("stale", True),
    )


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


def get_market_state(m: Metrics, tf: str, state: dict = None) -> StateResult:
    thr = THRESHOLDS[tf]
    c   = build_confirmation_data(state or {})

    all_scores = [ev(m, thr, c) for ev in ALL_EVALUATORS]
    active     = [s for s in all_scores if s.active]

    if not active:
        # Neutral
        return StateResult(
            label="Neutral", type="neutral", score=0.0, emoji="⚪",
            hits=0, total=0, confidence="None",
            primary_hits=0, primary_total=0,
            all_scores=all_scores,
        )

    # Conflict resolution: score → primary_hits → priority
    def sort_key(s: SignalScore):
        priority = SIGNAL_PRIORITY.get(s.label, 99)
        return (-s.score, -s.primary_hits, priority)

    active.sort(key=sort_key)
    winner = active[0]

    # Legacy score for backward compat (heatmap, history)
    legacy_score = winner.score * winner.total / 2

    return StateResult(
        label         = winner.label,
        type          = winner.type,
        score         = round(legacy_score, 4),
        emoji         = winner.emoji,
        hits          = winner.hits,
        total         = winner.total,
        confidence    = winner.confidence,
        primary_hits  = winner.primary_hits,
        primary_total = winner.primary_total,
        all_scores    = all_scores,
    )


# ----------------------------------------------------------
# Per-coin scoring
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
            symbol=f"{sym}USDT", rank=coin["rank"],
            altbtc_chg=altbtc_chg, vs_total2=vs_total2,
            score=score, hidden_signal=hidden,
        ))

    return scored


def get_top_strong(scores: list[CoinScore], n: int = 5) -> list[CoinScore]:
    return sorted(scores, key=lambda x: x.score, reverse=True)[:n]


def get_top_weak(scores: list[CoinScore], n: int = 5) -> list[CoinScore]:
    return sorted(scores, key=lambda x: x.score)[:n]