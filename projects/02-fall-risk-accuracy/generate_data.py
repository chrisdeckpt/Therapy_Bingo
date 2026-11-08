"""Generate a synthetic PACE-like cohort with four fall-risk screens and a 12-month fall outcome.

Each tool is a noisy reading of the same hidden 'fall propensity'. The new tool is given
slightly less noise (it is built to be sensitive), and the legacy tools get ceiling effects
like the real instruments. Output: data/synthetic_cohort.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 7
N = 300


def main() -> None:
    rng = np.random.default_rng(SEED)
    age = rng.normal(78, 7, N).clip(55, 100).round()
    female = rng.random(N) < 0.68
    risk = rng.normal(0, 1, N) + 0.03 * (age - 78)  # latent fall propensity

    # 12-month fall outcome. PACE participants fall often, so the target rate is about 40%.
    p_fall = 1 / (1 + np.exp(-(-0.45 + 1.4 * risk)))
    fell = rng.random(N) < p_fall

    def scale(x, noise):
        return x + rng.normal(0, noise, N)

    # New tool: 0-20, higher = more risk
    new_tool = np.clip(np.round(8 + 3.2 * scale(risk, 0.55)), 0, 20)
    # Berg Balance Scale: 0-56, lower = more risk, ceiling at 56
    berg = np.clip(np.round(44 - 7.5 * scale(risk, 0.8)), 0, 56)
    # Tinetti POMA: 0-28, lower = more risk
    tinetti = np.clip(np.round(20 - 4.0 * scale(risk, 0.9)), 0, 28)
    # SPPB: 0-12, lower = more risk
    sppb = np.clip(np.round(7 - 2.2 * scale(risk, 0.95)), 0, 12)

    df = pd.DataFrame(
        {
            "subject_id": [f"S{i:03d}" for i in range(1, N + 1)],
            "age": age.astype(int),
            "sex": np.where(female, "F", "M"),
            "new_tool": new_tool.astype(int),
            "berg": berg.astype(int),
            "tinetti": tinetti.astype(int),
            "sppb": sppb.astype(int),
            "fell_12mo": fell.astype(int),
        }
    )
    out = Path(__file__).parent / "data" / "synthetic_cohort.csv"
    out.parent.mkdir(exist_ok=True)
    df.to_csv(out, index=False)
    print(f"Wrote {N} rows to {out} (fall rate {fell.mean():.0%})")


if __name__ == "__main__":
    main()
