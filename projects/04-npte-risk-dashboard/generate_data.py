"""Generate synthetic, anonymized DPT cohort data.

data/history.csv  : 300 past graduates WITH a known NPTE first-attempt outcome (used to fit the model)
data/current.csv  : 40 current students WITHOUT an outcome (the cohort the dashboard stratifies)
"""
from pathlib import Path

import numpy as np
import pandas as pd

from risk_model import CONTENT_AREAS

SEED = 11
HERE = Path(__file__).parent


def make_cohort(n: int, rng: np.random.Generator, prefix: str, with_outcome: bool) -> pd.DataFrame:
    ability = rng.normal(0, 1, n)
    gpa = np.clip(3.45 + 0.25 * ability + rng.normal(0, 0.15, n), 2.6, 4.0).round(2)
    peat = np.clip(np.round(640 + 55 * ability + rng.normal(0, 30, n)), 400, 800).astype(int)
    hours = np.clip(np.round(rng.gamma(4, 30, n) + 15 * ability), 20, 450).astype(int)
    df = pd.DataFrame(
        {
            "student_id": [f"{prefix}{i:03d}" for i in range(1, n + 1)],
            "gpa": gpa,
            "peat_score": peat,
            "study_hours": hours,
        }
    )
    # Each student has a couple of personal weak spots, so the heatmap has real structure
    for area in CONTENT_AREAS:
        weak = rng.random(n) < 0.18
        pct = 68 + 8 * ability + rng.normal(0, 6, n) - weak * rng.uniform(8, 18, n)
        df[f"pe_{area}"] = np.clip(pct, 30, 98).round(1)
    if with_outcome:
        pe_mean = df[[f"pe_{a}" for a in CONTENT_AREAS]].mean(axis=1)
        logit = (-1.9 - 1.2 * (gpa - 3.45) - 0.010 * (peat - 640)
                 - 0.004 * (hours - 120) - 0.07 * (pe_mean - 66) + rng.normal(0, 0.5, n))
        df["npte_failed"] = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    return df


def main() -> None:
    rng = np.random.default_rng(SEED)
    (HERE / "data").mkdir(exist_ok=True)
    hist = make_cohort(300, rng, "H", with_outcome=True)
    cur = make_cohort(40, rng, "S", with_outcome=False)
    hist.to_csv(HERE / "data" / "history.csv", index=False)
    cur.to_csv(HERE / "data" / "current.csv", index=False)
    print(f"history.csv: {len(hist)} rows, failure rate {hist.npte_failed.mean():.0%}")
    print(f"current.csv: {len(cur)} rows")


if __name__ == "__main__":
    main()
