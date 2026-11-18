"""gta6-twitch-ccu-forecast-01 entry in Python 3.13 (standard library only).
"""

import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0, 0.674, 1.645]
SIGMA = 0.15


def round2(x: float) -> float | int:
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value.is_integer() else value


def weighted_median(values: list[float], weights: list[float]) -> float:
    if not values:
        return 0.0
    pairs = sorted(zip(values, weights), key=lambda x: x[0])
    total_w = sum(w for v, w in pairs)
    if total_w <= 0:
        return values[len(values) // 2]
    cum_w = 0.0
    target = 0.5 * total_w
    for v, w in pairs:
        cum_w += w
        if cum_w >= target:
            return v
    return pairs[-1][0]


def weighted_std(values: list[float], weights: list[float], mean: float) -> float:
    if not values or sum(weights) <= 0:
        return SIGMA
    total_w = sum(weights)
    var = sum(w * (v - mean) ** 2 for v, w in zip(values, weights)) / total_w
    return math.sqrt(max(0.0, var))


def forecast_case(case: dict, name: str) -> dict:
    if case.get("levels") != LEVELS:
        raise ValueError(f"{name} asks for levels {case['levels']}, not {LEVELS}")
    first = next((k for k in case.get("known", []) if k.get("hour") == 1), None)
    if first is None:
        raise ValueError(f"{name} has no hour-1 print")
    p1 = max(1, first.get("viewers", 1))

    # Collect log-ratios per hour h (2..24) across comparables
    comparables = case.get("comparables", [])
    hour_data = {h: [] for h in range(2, 25)}
    hour_weights = {h: [] for h in range(2, 25)}

    for comp in comparables:
        try:
            ds = comp.get("day_start")
            hourly = comp.get("hourly", [])
            if not ds or not hourly:
                continue
            match_idx = next((i for i, h in enumerate(hourly) if h.get("from") == ds), None)
            if match_idx is None or len(hourly) < match_idx + 24:
                continue
            v1 = hourly[match_idx].get("viewers", 0)
            if v1 <= 0:
                continue
            log_v1 = math.log(v1)

            # Weight determination
            platforms = comp.get("platforms", "")
            unlock = comp.get("unlock", "")
            c_name = comp.get("name", "")
            base_w = 1.0 if any(k in platforms.lower() for k in ["console", "playstation", "xbox"]) or "midnight" in unlock.lower() else 0.5
            if "gta" in c_name.lower() and "vi" in c_name.lower():
                weight = 0.5
            else:
                weight = base_w

            for h in range(2, 25):
                pt = hourly[match_idx + h - 1]
                vh = pt.get("viewers", 0)
                if vh > 0:
                    lr = math.log(vh) - log_v1
                    hour_data[h].append(lr)
                    hour_weights[h].append(weight)
        except Exception:
            continue

    # History trend for momentum
    trend = 0.0
    try:
        cp = case.get("checkpoint", "")
        hist_before = [h.get("viewers", 0) for h in case.get("history_hourly", []) if h.get("from", "") < cp and h.get("viewers", 0) > 0]
        if len(hist_before) >= 2:
            last3 = hist_before[-3:]
            v_first = max(1, last3[0])
            v_last = max(1, last3[-1])
            trend = math.log(v_last / v_first) / max(1, len(last3) - 1)
    except Exception:
        trend = 0.0
    trend_clamped = max(-0.1, min(0.1, trend))

    m_vals = {}
    s_vals = {}
    for h in range(2, 25):
        vals = hour_data[h]
        weights = hour_weights[h]
        if vals and sum(weights) > 0:
            mh = weighted_median(vals, weights)
            sh = weighted_std(vals, weights, mh)
            sh = max(0.15, min(0.8, sh))
        else:
            mh = 0.0
            sh = SIGMA * math.sqrt(h - 1)

        # Momentum nudge fading to 0 by hour 6
        nudge = 0.25 * trend_clamped * max(0.0, (6 - h) / 4.0)
        mh += nudge

        m_vals[h] = mh
        s_vals[h] = max(0.15, min(0.8, sh))

    hours_out = []
    for row in case.get("forecast", []):
        h = row.get("hour")
        if h is None:
            continue
        mh = m_vals.get(h, 0.0)
        sh = s_vals.get(h, SIGMA * math.sqrt(h - 1))
        q50 = p1 * math.exp(mh)
        q_list = []
        for z in Z:
            q_val = q50 * math.exp(z * sh)
            q_val = max(0.01, min(1e9, q_val))
            q_list.append(q_val)
        # Enforce non-decreasing
        for i in range(1, len(q_list)):
            if q_list[i] < q_list[i - 1]:
                q_list[i] = q_list[i - 1]
        hours_out.append({"hour": h, "q": [round2(q) for q in q_list]})

    return {"hours": hours_out}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        try:
            case = json.loads(path.read_text(encoding="utf-8"))
            forecast = forecast_case(case, path.name)
            (OUTPUT_DIR / f"{path.stem}.out").write_text(json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8")
        except Exception as e:
            print(f"Error processing {path.name}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
