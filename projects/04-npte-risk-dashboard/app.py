"""NPTE risk-stratification dashboard. Run with:  streamlit run app.py"""
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

import risk_model as rm

HERE = Path(__file__).parent
TIER_COLORS = {"Low": "#3b8b5a", "Moderate": "#d9a21b", "High": "#c0392b"}

st.set_page_config(page_title="NPTE Risk Dashboard", layout="wide")
st.title("NPTE risk stratification")
st.caption("Anonymized IDs only. Data shown is synthetic unless you upload your own files.")

# ---------------- data ----------------
with st.sidebar:
    st.header("Data")
    up_hist = st.file_uploader("Historical cohort (with npte_failed)", type="csv")
    up_cur = st.file_uploader("Current cohort", type="csv")
    st.header("Risk tiers")
    low_cut, high_cut = st.slider("Failure-probability cutoffs (Low | Moderate | High)",
                                  0.0, 1.0, rm.DEFAULT_TIERS, 0.01)
    st.header("Study plan")
    weekly_hours = st.number_input("Study hours per week", 4.0, 40.0, 15.0, 1.0)
    weeks = st.number_input("Weeks until exam", 1, 26, 8)


@st.cache_data
def load_csv(src):
    return pd.read_csv(src)


try:
    history = load_csv(up_hist if up_hist else HERE / "data" / "history.csv")
    current = load_csv(up_cur if up_cur else HERE / "data" / "current.csv")
except FileNotFoundError:
    st.error("No data found. Run `python generate_data.py` first, or upload CSVs in the sidebar.")
    st.stop()

missing_h = rm.check_columns(history, ("npte_failed",))
missing_c = rm.check_columns(current)
if missing_h or missing_c:
    st.error(f"Missing columns. Historical: {missing_h or 'none'}. Current: {missing_c or 'none'}.")
    st.stop()

model = rm.fit(history)
scored = rm.score(model, current, (low_cut, high_cut))

# ---------------- cohort view ----------------
tab_cohort, tab_student, tab_model = st.tabs(["Cohort", "Student", "Model"])

with tab_cohort:
    counts = scored["tier"].value_counts()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Students", len(scored))
    c2.metric("High risk", int(counts.get("High", 0)))
    c3.metric("Moderate risk", int(counts.get("Moderate", 0)))
    c4.metric("Low risk", int(counts.get("Low", 0)))

    st.subheader("Weak content areas across the cohort")
    st.caption(f"Practice-exam % correct. Students are sorted by risk (highest at top). Below {rm.WEAK_AREA_PCT:.0f}% counts as weak.")
    long = scored.melt(id_vars=["student_id", "tier", "fail_prob"], value_vars=rm.PE_COLS,
                       var_name="area", value_name="pct")
    long["area"] = long["area"].str.removeprefix("pe_").map(lambda k: rm.CONTENT_AREAS[k][0])
    order = scored["student_id"].tolist()
    heat = (
        alt.Chart(long)
        .mark_rect()
        .encode(
            x=alt.X("area:N", sort=[v[0] for v in rm.CONTENT_AREAS.values()], title=None,
                    axis=alt.Axis(orient="top", labelAngle=-35, labelLimit=220, labelOverlap=False)),
            y=alt.Y("student_id:N", sort=order, title=None, axis=alt.Axis(labelOverlap=False)),
            color=alt.Color("pct:Q", title="% correct",
                            scale=alt.Scale(scheme="redyellowgreen", domain=[45, 90], clamp=True)),
            tooltip=["student_id", "tier", alt.Tooltip("fail_prob:Q", format=".0%", title="fail risk"),
                     "area", alt.Tooltip("pct:Q", format=".1f")],
        )
        .properties(height=max(320, 18 * len(scored)))
    )
    st.altair_chart(heat, width="stretch")

    st.subheader("Cohort weak-area summary")
    area_summary = pd.DataFrame({
        "area": [v[0] for v in rm.CONTENT_AREAS.values()],
        "cohort mean %": [scored[c].mean() for c in rm.PE_COLS],
        f"students < {rm.WEAK_AREA_PCT:.0f}%": [int((scored[c] < rm.WEAK_AREA_PCT).sum()) for c in rm.PE_COLS],
    }).sort_values("cohort mean %")
    st.dataframe(area_summary.style.format({"cohort mean %": "{:.1f}"}), hide_index=True, width="stretch")

    st.subheader("Roster")
    roster = scored[["student_id", "tier", "fail_prob", "gpa", "peat_score", "study_hours", "pe_mean", "weak_areas"]]
    st.dataframe(
        roster.style.format({"fail_prob": "{:.0%}", "pe_mean": "{:.1f}", "gpa": "{:.2f}"})
        .map(lambda t: f"color: {TIER_COLORS.get(t, 'inherit')}; font-weight: 600", subset=["tier"]),
        hide_index=True, width="stretch",
    )
    st.download_button("Download roster CSV", roster.to_csv(index=False), "npte_risk_roster.csv")

# ---------------- student view ----------------
with tab_student:
    sid = st.selectbox("Student", scored["student_id"],
                       format_func=lambda s: f"{s}  ({scored.set_index('student_id').at[s, 'tier']} risk)")
    s = scored.set_index("student_id").loc[sid]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Failure risk: {s.tier} tier", f"{s.fail_prob:.0%}")
    c2.metric("GPA", f"{s.gpa:.2f}")
    c3.metric("PEAT", int(s.peat_score))
    c4.metric("Study hours logged", int(s.study_hours))

    plan = rm.study_plan(s, weekly_hours, int(weeks))
    left, right = st.columns([1, 1])
    with left:
        st.subheader("Practice exam vs cohort")
        comp = pd.DataFrame({
            "area": [v[0] for v in rm.CONTENT_AREAS.values()] * 2,
            "pct": [s[c] for c in rm.PE_COLS] + [scored[c].mean() for c in rm.PE_COLS],
            "who": [sid] * len(rm.PE_COLS) + ["Cohort mean"] * len(rm.PE_COLS),
        })
        bars = alt.Chart(comp).mark_bar().encode(
            y=alt.Y("area:N", title=None, sort=[v[0] for v in rm.CONTENT_AREAS.values()],
                    axis=alt.Axis(labelLimit=220)),
            x=alt.X("pct:Q", title="% correct", scale=alt.Scale(domain=[0, 100])),
            yOffset="who:N",
            color=alt.Color("who:N", title=None,
                            scale=alt.Scale(domain=[sid, "Cohort mean"], range=["#2e86ab", "#b8c2cc"])),
            tooltip=["who", "area", alt.Tooltip("pct:Q", format=".1f")],
        )
        rule = alt.Chart(pd.DataFrame({"x": [rm.WEAK_AREA_PCT]})).mark_rule(strokeDash=[4, 3], color="#c0392b").encode(x="x:Q")
        st.altair_chart(bars + rule, width="stretch")
    with right:
        st.subheader(f"Targeted plan: {weekly_hours:.0f} h/week × {int(weeks)} weeks")
        st.dataframe(
            plan[["area", "practice_pct", "hours_per_week", "total_hours", "recommendation"]]
            .style.format({"practice_pct": "{:.1f}", "hours_per_week": "{:.1f}", "total_hours": "{:.0f}"}),
            hide_index=True, width="stretch",
        )
        top = plan[plan.gap > 0].head(3)["area"].tolist()
        tips = []
        if top:
            tips.append(f"Spend most of your time on **{', '.join(top)}**. These areas combine the biggest gaps with heavy exam weight.")
        if s.tier == "High":
            tips.append("Book a faculty advising meeting and retake a full-length practice exam in 3–4 weeks.")
        if s.study_hours < scored.study_hours.median():
            tips.append(f"Logged hours ({int(s.study_hours)}) are below the cohort median ({int(scored.study_hours.median())}).")
        for t in tips:
            st.markdown(f"- {t}")
    st.caption("Hours are split by gap below 75% × approximate NPTE content weight, with 0.5 h/week of maintenance for every area.")

# ---------------- model view ----------------
with tab_model:
    st.markdown(
        f"Logistic regression trained on **{model.n_train}** past graduates "
        f"(failure rate {model.fail_rate:.0%}). Cross-validated AUC: **{model.cv_auc:.2f}**."
    )
    coefs = model.coefficients()
    st.dataframe(coefs.style.format({"coef_per_SD": "{:+.2f}", "odds_ratio_per_SD": "{:.2f}"}),
                 hide_index=True)
    st.caption("Odds ratios are per 1 SD increase in each predictor. Below 1 means the predictor protects against failure. "
               "This is a screening aid, not a decision rule. Check calibration on your own program's outcomes before you act on it.")
