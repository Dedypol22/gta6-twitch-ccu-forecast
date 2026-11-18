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


def round2(x: float) -> float | int:
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value.is_integer() else value


def forecast_case(case: dict, name: str) -> dict:
    if case.get("levels") != LEVELS:
        raise ValueError(f"{name} asks for levels {case['levels']}, not {LEVELS}")
    first = next((k for k in case.get("known", []) if k.get("hour") == 1), None)
    if first is None:
        raise ValueError(f"{name} has no hour-1 print")
    p1 = max(1, first.get("viewers", 1))
    lp1 = math.log(p1)

    # Collect data per hour
    comparables = case.get("comparables", [])
    hour_lr = {h: [] for h in range(2, 25)}
    hour_x = {h: [] for h in range(2, 25)}
    hour_kw = {h: [] for h in range(2, 25)}

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
            lv1 = math.log(v1)
            x = lv1 - lp1

            # Base weight
            platforms = comp.get("platforms", "").lower()
            unlock = comp.get("unlock", "").lower()
            c_name = comp.get("name", "").lower()
            
            w = 1.0 if any(k in platforms for k in ["console", "playstation", "xbox"]) or "midnight" in unlock else 0.5
            if "gta" in c_name and "vi" in c_name:
                w = 0.5
            
            # Platform multipliers
            if ("playstation 5" in platforms or "ps5" in platforms) and "xbox" not in platforms:
                w *= 1.5
            elif "xbox" in platforms and not any(k in platforms for k in ["playstation", "ps"]):
                w *= 0.75
            
            kw = w * math.exp(-((lv1 - lp1) / 2.0)**2)

            for h in range(2, 25):
                vh = hourly[match_idx + h - 1].get("viewers", 0)
                if vh > 0:
                    lr = math.log(vh) - lv1
                    hour_lr[h].append(lr)
                    hour_x[h].append(x)
                    hour_kw[h].append(kw)
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
        lrs = hour_lr[h]
        xs = hour_x[h]
        kws = hour_kw[h]
        total_kw = sum(kws)
        
        if total_kw > 0:
            mean_lr = sum(lr * kw for lr, kw in zip(lrs, kws)) / total_kw
            mean_x = sum(x * kw for x, kw in zip(xs, kws)) / total_kw
            
            num = sum(kw * (x - mean_x) * (lr - mean_lr) for x, lr, kw in zip(xs, lrs, kws))
            den = sum(kw * (x - mean_x)**2 for x, kw in zip(xs, kws))
            b = max(-1.0, min(1.0, num / den if den > 1e-9 else 0.0))
            
            mh = mean_lr - b * mean_x
            
            res_var = sum(kw * (lr - (mean_lr + b * (x - mean_x)))**2 for x, lr, kw in zip(xs, lrs, kws)) / total_kw
            sh = math.sqrt(max(0.0, res_var))
            sh = max(0.15, min(0.8, sh))
        else:
            mh = 0.0
            sh = 0.15 * math.sqrt(h - 1)

        # Momentum nudge
        nudge = 0.25 * trend_clamped * max(0.0, (6 - h) / 4.0)
        m_vals[h] = mh + nudge
        s_vals[h] = sh

    hours_out = []
    for row in case.get("forecast", []):
        h = row.get("hour")
        if h is None: continue
        mh = m_vals.get(h, 0.0)
        sh = s_vals.get(h, 0.15 * math.sqrt(h - 1))
        
        q_list = []
        for z in Z:
            q_val = p1 * math.exp(mh + z * sh)
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
