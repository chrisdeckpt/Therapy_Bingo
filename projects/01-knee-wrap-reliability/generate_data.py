"""Generate a synthetic intrarater reliability dataset for a knee-wrap BFR study.

20 participants x 2 pressure conditions (low / high limb occlusion pressure)
x 3 trials, measuring achieved cuff/wrap pressure in mmHg.
Output: data/synthetic_trials.csv (long format).
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_PARTICIPANTS = 20
N_TRIALS = 3
# Target pressures as a percentage of each participant's full limb occlusion pressure (LOP)
CONDITIONS = {"low": 0.40, "high": 0.80}
TRIAL_SD = {"low": 4.0, "high": 6.0}  # within-person trial-to-trial noise, mmHg


def main() -> None:
    rng = np.random.default_rng(SEED)
    rows = []
    lop = rng.normal(180, 22, N_PARTICIPANTS).clip(130, 240)  # full LOP per participant
    for i in range(N_PARTICIPANTS):
        pid = f"P{i + 1:02d}"
        for cond, pct in CONDITIONS.items():
            target = lop[i] * pct
            wrap_bias = rng.normal(0, 3)  # how this participant's limb tends to take the wrap
            for t in range(1, N_TRIALS + 1):
                learning = -0.8 * (t - 1)  # small systematic drift across trials
                achieved = target + wrap_bias + learning + rng.normal(0, TRIAL_SD[cond])
                rows.append(
                    {
                        "participant_id": pid,
                        "condition": cond,
                        "trial": t,
                        "pressure_mmhg": round(achieved, 1),
                    }
                )
    out = Path(__file__).parent / "data" / "synthetic_trials.csv"
    out.parent.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"Wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
