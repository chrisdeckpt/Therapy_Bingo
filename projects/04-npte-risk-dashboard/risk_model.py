"""Risk model and study-plan logic (no Streamlit here, so it can be tested on its own)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

# NPTE content areas tracked from practice exams. Weights are the APPROXIMATE share of NPTE items
# per area. Check them against the current FSBPT content outline before relying on them.
CONTENT_AREAS = {
    "musculoskeletal": ("Musculoskeletal", 0.23),
    "neuromuscular": ("Neuromuscular", 0.20),
    "cardiopulmonary": ("Cardiopulmonary & vascular", 0.13),
    "integumentary": ("Integumentary", 0.05),
    "other_systems": ("Other systems (metabolic, GI, GU)", 0.10),
    "equipment_modalities": ("Equipment, devices & modalities", 0.11),
    "safety_professional": ("Safety & professional roles", 0.10),
    "research_ebp": ("Research & EBP", 0.08),
}
PE_COLS = [f"pe_{a}" for a in CONTENT_AREAS]
FEATURES = ["gpa", "peat_score", "study_hours", "pe_mean"]
REQUIRED = ["student_id", "gpa", "peat_score", "study_hours", *PE_COLS]

DEFAULT_TIERS = (0.15, 0.35)  # probability cutoffs: < low_cut = Low, >= high_cut = High
WEAK_AREA_PCT = 65.0          # practice-exam % below which an area counts as weak


def check_columns(df: pd.DataFrame, extra: tuple[str, ...] = ()) -> list[str]:
    return [c for c in [*REQUIRED, *extra] if c not in df.columns]


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["pe_mean"] = out[PE_COLS].mean(axis=1)
    return out


@dataclass
class FittedModel:
    pipeline: object
    cv_auc: float
    n_train: int
    fail_rate: float

    def coefficients(self) -> pd.DataFrame:
        lr = self.pipeline.named_steps["logisticregression"]
        coefs = pd.DataFrame({"feature": FEATURES, "coef_per_SD": lr.coef_[0]})
        coefs["odds_ratio_per_SD"] = np.exp(coefs["coef_per_SD"])
        return coefs


def fit(history: pd.DataFrame) -> FittedModel:
    h = add_features(history)
    X, y = h[FEATURES], h["npte_failed"].astype(int)
    pipe = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
    folds = int(min(5, y.sum(), (1 - y).sum()))
    cv_auc = float(cross_val_score(pipe, X, y, cv=folds, scoring="roc_auc").mean()) if folds >= 2 else float("nan")
    pipe.fit(X, y)
    return FittedModel(pipe, cv_auc, len(h), float(y.mean()))


def tier(p: float, cuts: tuple[float, float] = DEFAULT_TIERS) -> str:
    return "Low" if p < cuts[0] else ("Moderate" if p < cuts[1] else "High")


def score(model: FittedModel, current: pd.DataFrame, cuts=DEFAULT_TIERS) -> pd.DataFrame:
    c = add_features(current)
    c["fail_prob"] = model.pipeline.predict_proba(c[FEATURES])[:, 1]
    c["tier"] = c["fail_prob"].apply(lambda p: tier(p, cuts))
    c["weak_areas"] = c[PE_COLS].lt(WEAK_AREA_PCT).sum(axis=1)
    return c.sort_values("fail_prob", ascending=False).reset_index(drop=True)


def study_plan(student: pd.Series, weekly_hours: float = 15, weeks: int = 8) -> pd.DataFrame:
    """Allocate weekly study hours by (gap below target) x (approximate exam weight).

    Every area keeps at least 0.5 h/week for maintenance. The rest goes to areas below 75%.
    """
    target = 75.0
    rows = []
    for key, (label, weight) in CONTENT_AREAS.items():
        pct = float(student[f"pe_{key}"])
        gap = max(0.0, target - pct)
        rows.append({"area": label, "practice_pct": pct, "exam_weight": weight, "gap": gap,
                     "priority": gap * weight})
    plan = pd.DataFrame(rows)
    maintenance = 0.5
    pool = max(0.0, weekly_hours - maintenance * len(plan))
    total_pri = plan["priority"].sum()
    if total_pri > 0:
        plan["hours_per_week"] = maintenance + pool * plan["priority"] / total_pri
    else:
        plan["hours_per_week"] = weekly_hours * plan["exam_weight"] / plan["exam_weight"].sum()
    plan["hours_per_week"] = plan["hours_per_week"].round(1)
    plan["total_hours"] = (plan["hours_per_week"] * weeks).round(0)

    def focus(r):
        if r.practice_pct < WEAK_AREA_PCT:
            return "Priority: content review + timed question blocks"
        if r.practice_pct < target:
            return "Targeted questions + review missed items"
        return "Maintain: mixed question sets"

    plan["recommendation"] = plan.apply(focus, axis=1)
    return plan.sort_values("priority", ascending=False).reset_index(drop=True)
