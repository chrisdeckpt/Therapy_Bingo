"""Compare diagnostic accuracy of four fall-risk screens against 12-month falls.

For each tool:
  * sensitivity, specificity, PPV, NPV, LR+, LR- at the published cutoff
  * AUC with a bootstrap 95% CI
  * the cutoff that maximizes sensitivity while keeping specificity >= MIN_SPECIFICITY
Outputs: results.csv, roc_curves.png, report.html

Usage:
    python analysis.py
    python analysis.py --input data/my_cohort.csv --min-spec 0.6
"""
from __future__ import annotations

import argparse
import base64
import html
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, roc_curve

HERE = Path(__file__).parent
OUTCOME = "fell_12mo"

# Edit this to change tools or cutoffs. "risk_if" says which side of the cutoff counts as a positive screen.
# CHECK THESE AGAINST THE SOURCES YOU CITE. Published cutoffs vary by population.
TOOLS = {
    "new_tool": {"label": "New tool", "cutoff": 8, "risk_if": ">=", "color": "#d1495b",
                 "source": "Placeholder: set to your tool's derivation cutoff"},
    "berg": {"label": "Berg Balance Scale", "cutoff": 45, "risk_if": "<=", "color": "#2e86ab",
             "source": "≤45/56 (Berg et al., 1992)"},
    "tinetti": {"label": "Tinetti POMA", "cutoff": 18, "risk_if": "<=", "color": "#3b8b5a",
                "source": "≤18/28 high risk (Tinetti, 1986)"},
    "sppb": {"label": "SPPB", "cutoff": 9, "risk_if": "<=", "color": "#8e6c8a",
             "source": "≤9/12 (Guralnik et al., 1994; Veronese et al., 2014)"},
}
MIN_SPECIFICITY = 0.50
N_BOOT = 1000


def positive(scores: pd.Series, cutoff: float, risk_if: str) -> np.ndarray:
    return (scores >= cutoff).to_numpy() if risk_if == ">=" else (scores <= cutoff).to_numpy()


def risk_oriented(scores: pd.Series, risk_if: str) -> np.ndarray:
    """Flip scores so that higher always means more risk (needed for ROC/AUC)."""
    return scores.to_numpy() if risk_if == ">=" else -scores.to_numpy()


def safe_div(a: float, b: float) -> float:
    return a / b if b else float("nan")


def accuracy(y: np.ndarray, pos: np.ndarray) -> dict:
    tp = int((pos & (y == 1)).sum())
    fp = int((pos & (y == 0)).sum())
    fn = int((~pos & (y == 1)).sum())
    tn = int((~pos & (y == 0)).sum())
    sens, spec = safe_div(tp, tp + fn), safe_div(tn, tn + fp)
    return {
        "TP": tp, "FP": fp, "FN": fn, "TN": tn,
        "sensitivity": sens,
        "specificity": spec,
        "PPV": safe_div(tp, tp + fp),
        "NPV": safe_div(tn, tn + fn),
        "LR_pos": safe_div(sens, 1 - spec),
        "LR_neg": safe_div(1 - sens, spec),
    }


def best_sensitive_cutoff(y: np.ndarray, scores: pd.Series, risk_if: str, min_spec: float):
    best = None
    for c in np.unique(scores):
        m = accuracy(y, positive(scores, c, risk_if))
        if m["specificity"] < min_spec:
            continue
        key = (m["sensitivity"], m["specificity"])
        if best is None or key > best[0]:
            best = (key, c, m)
    return (None, None) if best is None else (best[1], best[2])


def bootstrap_auc(y: np.ndarray, s: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    aucs = []
    n = len(y)
    for _ in range(N_BOOT):
        idx = rng.integers(0, n, n)
        if y[idx].min() == y[idx].max():
            continue
        aucs.append(roc_auc_score(y[idx], s[idx]))
    return float(np.percentile(aucs, 2.5)), float(np.percentile(aucs, 97.5))


def plot_roc(df: pd.DataFrame, rows: list[dict], path: Path) -> None:
    y = df[OUTCOME].to_numpy()
    fig, ax = plt.subplots(figsize=(6.2, 5.6))
    ax.plot([0, 1], [0, 1], color="#bbb", lw=1, ls="--")
    for r in rows:
        cfg = TOOLS[r["tool"]]
        fpr, tpr, _ = roc_curve(y, risk_oriented(df[r["tool"]], cfg["risk_if"]))
        ax.plot(fpr, tpr, color=cfg["color"], lw=2, label=f"{cfg['label']} (AUC {r['AUC']:.2f})")
        ax.scatter(1 - r["specificity"], r["sensitivity"], color=cfg["color"], s=45, zorder=3,
                   edgecolor="white")
    ax.axvline(1 - MIN_SPECIFICITY, color="#888", lw=0.8, ls=":")
    ax.text(1 - MIN_SPECIFICITY + 0.01, 0.96, f"specificity = {MIN_SPECIFICITY:.2f}", fontsize=8, color="#666")
    ax.set_xlabel("1 − Specificity")
    ax.set_ylabel("Sensitivity")
    ax.set_title("ROC curves: 12-month falls\n(dots = published cutoffs)", fontsize=11)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.01)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="lower right", frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fmt(x, nd=2):
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{nd}f}"


def write_html(df: pd.DataFrame, res: pd.DataFrame, roc_png: Path, path: Path, min_spec: float) -> None:
    img = base64.b64encode(roc_png.read_bytes()).decode()
    n, falls = len(df), int(df[OUTCOME].sum())

    def row(r):
        cfg = TOOLS[r.tool]
        return (
            f"<tr><td><span class='sw' style='background:{cfg['color']}'></span>{html.escape(cfg['label'])}</td>"
            f"<td>{r.risk_if} {fmt(r.published_cutoff, 0)}</td><td>{fmt(r.sensitivity)}</td><td>{fmt(r.specificity)}</td>"
            f"<td>{fmt(r.PPV)}</td><td>{fmt(r.NPV)}</td><td>{fmt(r.LR_pos)}</td><td>{fmt(r.LR_neg)}</td>"
            f"<td>{fmt(r.AUC)} <span class='ci'>({fmt(r.AUC_lower)}–{fmt(r.AUC_upper)})</span></td>"
            f"<td>{r.risk_if} {fmt(r.opt_cutoff, 0)}</td><td>{fmt(r.opt_sensitivity)} / {fmt(r.opt_specificity)}</td></tr>"
        )

    best = res.loc[res["opt_sensitivity"].idxmax()]
    top_auc = res.loc[res["AUC"].idxmax()]
    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fall-Risk Screen Comparison</title>
<style>
:root{{--bg:#fff;--fg:#1d2433;--muted:#5c6577;--line:#e3e6ec;--card:#f7f8fa}}
@media (prefers-color-scheme:dark){{:root{{--bg:#14171c;--fg:#e6e9ef;--muted:#9aa3b2;--line:#2a2f38;--card:#1b1f26}}}}
body{{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif;margin:0;padding:24px 16px}}
main{{max-width:980px;margin:0 auto}} h1{{font-size:22px;margin:0 0 4px}} .sub{{color:var(--muted);margin:0 0 18px}}
.grid{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:20px;align-items:start}}
@media (max-width:760px){{.grid{{grid-template-columns:1fr}}}}
img{{max-width:100%;background:#fff;border-radius:8px}} .card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}}
.wrap{{overflow-x:auto}} table{{border-collapse:collapse;width:100%;font-size:13px;margin-top:18px}}
th,td{{padding:6px 8px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}} th:first-child,td:first-child{{text-align:left}}
th{{color:var(--muted);font-weight:600}} .ci{{color:var(--muted);font-size:12px}}
.sw{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}} ul{{padding-left:18px;margin:6px 0}}
.foot{{color:var(--muted);font-size:12px;margin-top:14px}}
</style></head><body><main>
<h1>Fall-risk screen comparison</h1>
<p class="sub">{n} participants · {falls} fallers in 12 months ({falls / n:.0%}) · published cutoffs vs a sensitivity-first cutoff (specificity ≥ {min_spec:.2f})</p>
<div class="grid">
  <img src="data:image/png;base64,{img}" alt="Overlaid ROC curves for the four screening tools">
  <div class="card"><strong>Key findings</strong><ul>
    <li>Highest AUC: <b>{html.escape(TOOLS[top_auc.tool]['label'])}</b> ({fmt(top_auc.AUC)}, 95% CI {fmt(top_auc.AUC_lower)}–{fmt(top_auc.AUC_upper)}).</li>
    <li>Highest sensitivity with specificity ≥ {min_spec:.2f}: <b>{html.escape(TOOLS[best.tool]['label'])}</b> at {best.risk_if} {fmt(best.opt_cutoff, 0)}
        (sensitivity {fmt(best.opt_sensitivity)}, specificity {fmt(best.opt_specificity)}).</li>
    {''.join(f"<li>{html.escape(TOOLS[r.tool]['label'])}: published cutoff sensitivity {fmt(r.sensitivity)}, specificity {fmt(r.specificity)}, LR− {fmt(r.LR_neg)}.</li>" for r in res.itertuples())}
  </ul><p class="foot">These AUC CIs are unpaired bootstrap intervals. To claim one tool beats another, use a paired test such as DeLong's.</p></div>
</div>
<div class="wrap"><table>
<thead><tr><th>Tool</th><th>Published cutoff</th><th>Sens</th><th>Spec</th><th>PPV</th><th>NPV</th><th>LR+</th><th>LR−</th><th>AUC (95% CI)</th><th>Sensitivity-first cutoff</th><th>Sens / Spec</th></tr></thead>
<tbody>{''.join(row(r) for r in res.itertuples())}</tbody></table></div>
<p class="foot">Cutoff sources: {'; '.join(html.escape(f"{c['label']}: {c['source']}") for c in TOOLS.values())}.
AUC CIs: {N_BOOT} bootstrap resamples. PPV and NPV depend on the fall rate in this sample. Data are synthetic unless replaced.</p>
</main></body></html>"""
    path.write_text(doc)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", type=Path, default=HERE / "data" / "synthetic_cohort.csv")
    ap.add_argument("--outdir", type=Path, default=HERE / "output")
    ap.add_argument("--min-spec", type=float, default=MIN_SPECIFICITY)
    args = ap.parse_args()

    df = pd.read_csv(args.input)
    missing = ({OUTCOME} | set(TOOLS)) - set(df.columns)
    if missing:
        raise SystemExit(f"Input is missing columns: {sorted(missing)}")
    df = df.dropna(subset=[OUTCOME, *TOOLS])
    y = df[OUTCOME].astype(int).to_numpy()
    rng = np.random.default_rng(2024)
    args.outdir.mkdir(parents=True, exist_ok=True)

    rows = []
    for tool, cfg in TOOLS.items():
        pub = accuracy(y, positive(df[tool], cfg["cutoff"], cfg["risk_if"]))
        s = risk_oriented(df[tool], cfg["risk_if"])
        auc = roc_auc_score(y, s)
        lo, hi = bootstrap_auc(y, s, rng)
        opt_c, opt = best_sensitive_cutoff(y, df[tool], cfg["risk_if"], args.min_spec)
        rows.append({
            "tool": tool,
            "risk_if": cfg["risk_if"],
            "published_cutoff": cfg["cutoff"],
            **pub,
            "AUC": auc, "AUC_lower": lo, "AUC_upper": hi,
            "opt_cutoff": opt_c,
            "opt_sensitivity": opt["sensitivity"] if opt else np.nan,
            "opt_specificity": opt["specificity"] if opt else np.nan,
            "opt_LR_neg": opt["LR_neg"] if opt else np.nan,
        })
    res = pd.DataFrame(rows)
    res.round(4).to_csv(args.outdir / "results.csv", index=False)
    roc_png = args.outdir / "roc_curves.png"
    plot_roc(df, rows, roc_png)
    write_html(df, res, roc_png, args.outdir / "report.html", args.min_spec)
    print(res[["tool", "sensitivity", "specificity", "AUC", "opt_cutoff", "opt_sensitivity", "opt_specificity"]]
          .round(3).to_string(index=False))
    print(f"\nSaved results.csv, roc_curves.png, report.html to {args.outdir}")


if __name__ == "__main__":
    main()
