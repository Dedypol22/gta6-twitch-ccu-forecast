# GTA VI Twitch CCU Forecast

[![make.fun](https://img.shields.io/badge/make.fun-gta6--twitch--ccu--forecast--01-blue)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)

Forecasts Grand Theft Auto VI's launch-day Twitch concurrent viewers (CCU) hour by hour (hours 2..24) using historical comparables and pre-launch momentum weighting.

## Method
- **Comparables Normalization**: Normalizes hourly viewer curves of past major game launches relative to their hour-1 print using log ratios.
- **Weighted Aggregation**: Computes weighted medians and standard deviations across comparables, favoring console-native launches and local midnight unlocks, while adjusting weights for pre-launch hype regimes.
- **Momentum Blending**: Integrates recent pre-launch history trend to capture launch momentum into hours 2–4, fading smoothly to baseline by hour 6.
- **Quantile Generation**: Generates 5 quantile levels `[0.05, 0.25, 0.50, 0.75, 0.95]` assuming log-normal spread around the forecasted median, enforced non-decreasing.

## Run Instructions
```bash
MAKEFUN_INPUT_DIR=/input MAKEFUN_OUTPUT_DIR=/output python3 -P -s main.py
```
