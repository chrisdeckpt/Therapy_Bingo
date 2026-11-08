"""Intrarater reliability analysis for knee-wrap BFR pressure.

For each pressure condition computes:
  * ICC(3,1) and ICC(3,k) (two-way mixed, consistency; Shrout & Fleiss 1979)
    with 95% CIs (McGraw & Wong 1996, F-distribution method)
  * SEM = SD * sqrt(1 - ICC(3,1))
  * MDC95 = SEM * 1.96 * sqrt(2)
  * Bland-Altman plots for each pair of trials

Usage:
    python analysis.py                          # uses data/synthetic_trials.csv
    python analysis.py --input data/my_data.csv # your own data (see README)
"""
from __future__ import annotations

import argparse
from itertools import combinations
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).parent
REQUIRED_COLS = {"participant_id", "condition", "trial", "pressure_mmhg"}


def icc3(wide: np.ndarray, alpha: float = 0.05) -> dict:
    """ICC(3,1) and ICC(3,k) with CIs from an n-subjects x k-trials matrix."""
    n, k = wide.shape
    grand = wide.mean()
    ss_total = ((wide - grand) ** 2).sum()
    ss_rows = k * ((wide.mean(axis=1) - grand) ** 2).sum()
    ss_cols = n * ((wide.mean(axis=0) - grand) ** 2).sum()
    ss_err = ss_total - ss_rows - ss_cols
    df_r, df_e = n - 1, (n - 1) * (k - 1)
    msr, mse = ss_rows / df_r, ss_err / df_e

    icc_1 = (msr - mse) / (msr + (k - 1) * mse)
    icc_k = (msr - mse) / msr

    f_obs = msr / mse
    f_l = f_obs / stats.f.ppf(1 - alpha / 2, df_r, df_e)
    f_u = f_obs * stats.f.ppf(1 - alpha / 2, df_e, df_r)
    return {
        "n": n,
        "k": k,
        "ICC_3_1": icc_1,
        "ICC_3_1_lower": (f_l - 1) / (f_l + k - 1),
        "ICC_3_1_upper": (f_u - 1) / (f_u + k - 1),
        "ICC_3_k": icc_k,
        "ICC_3_k_lower": 1 - 1 / f_l,
        "ICC_3_k_upper": 1 - 1 / f_u,
        "F": f_obs,
        "p": stats.f.sf(f_obs, df_r, df_e),
    }


def interpret_icc(icc: float) -> str:
    """Koo & Li (2016) thresholds."""
    if icc < 0.5:
        return "poor"
    if icc < 0.75:
        return "moderate"
    if icc < 0.9:
        return "good"
    return "excellent"


def load(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        raise SystemExit(f"Input is missing columns: {sorted(missing)}")
    return df


def to_wide(df: pd.DataFrame) -> pd.DataFrame:
    wide = df.pivot_table(index="participant_id", columns="trial", values="pressure_mmhg")
    dropped = wide.isna().any(axis=1).sum()
    if dropped:
        print(f"  note: dropping {dropped} participant(s) with missing trials")
    return wide.dropna()


def bland_altman(wide: pd.DataFrame, condition: str, out_dir: Path) -> list[dict]:
    pairs = list(combinations(wide.columns, 2))
    fig, axes = plt.subplots(1, len(pairs), figsize=(5 * len(pairs), 4.2), squeeze=False)
    summaries = []
    for ax, (a, b) in zip(axes[0], pairs):
        mean = (wide[a] + wide[b]) / 2
        diff = wide[a] - wide[b]
        bias, sd = diff.mean(), diff.std(ddof=1)
        lo, hi = bias - 1.96 * sd, bias + 1.96 * sd
        ax.scatter(mean, diff, s=28, color="#2a6f97", alpha=0.85)
        ax.axhline(bias, color="#333", lw=1.2, label=f"Bias {bias:+.1f}")
        ax.axhline(lo, color="#c0392b", ls="--", lw=1, label=f"LoA {lo:.1f} to {hi:.1f}")
        ax.axhline(hi, color="#c0392b", ls="--", lw=1)
        ax.axhline(0, color="#999", lw=0.6)
        ax.set_title(f"Trial {a} vs Trial {b}")
        ax.set_xlabel("Mean of trials (mmHg)")
        ax.set_ylabel(f"Trial {a} − Trial {b} (mmHg)")
        ax.legend(fontsize=8, loc="best", frameon=False)
        ax.spines[["top", "right"]].set_visible(False)
        # Proportional bias: regress the difference on the mean
        reg = stats.linregress(mean, diff)
        summaries.append(
            {
                "condition": condition,
                "pair": f"T{a}-T{b}",
                "bias": bias,
                "loa_lower": lo,
                "loa_upper": hi,
                "prop_bias_slope": reg.slope,
                "prop_bias_p": reg.pvalue,
            }
        )
    fig.suptitle(f"Bland-Altman: {condition} pressure condition", fontweight="bold")
    fig.tight_layout()
    path = out_dir / f"bland_altman_{condition}.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  saved {path.relative_to(HERE) if path.is_relative_to(HERE) else path}")
    return summaries


def write_report(summary: pd.DataFrame, ba: pd.DataFrame, out_path: Path) -> None:
    lines = ["# Results", ""]
    n = int(summary["n"].iloc[0])
    k = int(summary["k"].iloc[0])
    sentences = []
    for _, r in summary.iterrows():
        sentences.append(
            f"At the {r.condition} limb occlusion pressure condition (mean {r.mean_mmhg:.1f} ± "
            f"{r.sd_mmhg:.1f} mmHg), intrarater reliability was {interpret_icc(r.ICC_3_1)} "
            f"for a single trial (ICC(3,1) = {r.ICC_3_1:.2f}, 95% CI {r.ICC_3_1_lower:.2f}–{r.ICC_3_1_upper:.2f}) "
            f"and {interpret_icc(r.ICC_3_k)} for the mean of {k} trials "
            f"(ICC(3,{k}) = {r.ICC_3_k:.2f}, 95% CI {r.ICC_3_k_lower:.2f}–{r.ICC_3_k_upper:.2f}). "
            f"The SEM was {r.SEM_mmhg:.1f} mmHg and the MDC95 was {r.MDC95_mmhg:.1f} mmHg."
        )
    lines.append(
        f"**Results:** {n} participants completed {k} trials of knee-wrap application at each pressure "
        f"condition. " + " ".join(sentences)
    )
    lines.append("")
    ba_bits = []
    for cond, g in ba.groupby("condition", sort=False):
        worst = g.loc[g["bias"].abs().idxmax()]
        ba_bits.append(
            f"{cond} condition: largest mean bias {worst.bias:+.1f} mmHg ({worst.pair}), "
            f"limits of agreement across trial pairs ranged from {g.loa_lower.min():.1f} to {g.loa_upper.max():.1f} mmHg"
        )
    prop = ba[ba["prop_bias_p"] < 0.05]
    if prop.empty:
        prop_text = "No pair of trials showed significant proportional bias (regression of difference on mean, all p ≥ 0.05)"
    else:
        prop_text = "Significant proportional bias was found for " + ", ".join(
            f"{r.condition} {r.pair} (slope {r.prop_bias_slope:.2f}, p = {r.prop_bias_p:.3f})" for r in prop.itertuples()
        )
    lines.append("Bland-Altman analysis: " + "; ".join(ba_bits) + ". " + prop_text + ".")
    lines += [
        "",
        "## Summary table",
        "",
        "| Condition | Mean ± SD (mmHg) | ICC(3,1) [95% CI] | ICC(3,k) [95% CI] | SEM (mmHg) | MDC95 (mmHg) |",
        "|---|---|---|---|---|---|",
    ]
    for _, r in summary.iterrows():
        lines.append(
            f"| {r.condition} | {r.mean_mmhg:.1f} ± {r.sd_mmhg:.1f} | "
            f"{r.ICC_3_1:.2f} [{r.ICC_3_1_lower:.2f}, {r.ICC_3_1_upper:.2f}] | "
            f"{r.ICC_3_k:.2f} [{r.ICC_3_k_lower:.2f}, {r.ICC_3_k_upper:.2f}] | "
            f"{r.SEM_mmhg:.1f} | {r.MDC95_mmhg:.1f} |"
        )
    lines += [
        "",
        "_ICC interpretation per Koo & Li (2016): <0.50 poor, 0.50–0.75 moderate, 0.75–0.90 good, >0.90 excellent. "
        "SEM = SD × √(1 − ICC(3,1)); MDC95 = SEM × 1.96 × √2._",
        "",
        "Bland-Altman plots: " + ", ".join(f"`bland_altman_{c}.png`" for c in summary["condition"]),
        "",
    ]
    out_path.write_text("\n".join(lines))
    print(f"  saved {out_path.relative_to(HERE) if out_path.is_relative_to(HERE) else out_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", type=Path, default=HERE / "data" / "synthetic_trials.csv")
    ap.add_argument("--outdir", type=Path, default=HERE / "output")
    args = ap.parse_args()

    df = load(args.input)
    args.outdir.mkdir(parents=True, exist_ok=True)
    rows, ba_rows = [], []
    for cond in df["condition"].drop_duplicates():
        print(f"Condition: {cond}")
        wide = to_wide(df[df["condition"] == cond])
        res = icc3(wide.to_numpy())
        sd = wide.to_numpy().std(ddof=1)
        sem = sd * np.sqrt(1 - res["ICC_3_1"])
        rows.append(
            {
                "condition": cond,
                **res,
                "mean_mmhg": wide.to_numpy().mean(),
                "sd_mmhg": sd,
                "SEM_mmhg": sem,
                "MDC95_mmhg": sem * 1.96 * np.sqrt(2),
            }
        )
        ba_rows += bland_altman(wide, cond, args.outdir)

    summary = pd.DataFrame(rows)
    ba = pd.DataFrame(ba_rows)
    summary.round(4).to_csv(args.outdir / "reliability_summary.csv", index=False)
    ba.round(3).to_csv(args.outdir / "bland_altman_summary.csv", index=False)
    print("  saved output/reliability_summary.csv, output/bland_altman_summary.csv")
    write_report(summary, ba, args.outdir / "results_report.md")
    print()
    print(summary[["condition", "ICC_3_1", "ICC_3_k", "SEM_mmhg", "MDC95_mmhg"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
