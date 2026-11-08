# Projects

Five standalone projects, each in its own folder with its own README. Everything runs on
**synthetic data**. Keep real patient or student data out of this repository. Each project's
`.gitignore` excludes everything in `data/` except the synthetic files.

| # | Folder | What it does | Run |
|---|---|---|---|
| 1 | [`01-knee-wrap-reliability`](01-knee-wrap-reliability) | ICC(3,1)/ICC(3,k) with 95% CIs, SEM, MDC95, and Bland-Altman plots for a knee-wrap BFR study, plus an APTA-style results paragraph | `python generate_data.py && python analysis.py` |
| 2 | [`02-fall-risk-accuracy`](02-fall-risk-accuracy) | Sensitivity, specificity, PPV, NPV, LRs, and AUC for a new fall screen against Berg, Tinetti, and SPPB, a sensitivity-first cutoff search, overlaid ROC curves, and a one-page HTML report | `python generate_data.py && python analysis.py` |
| 3 | [`03-rounds-game`](03-rounds-game) | Browser game: sort 16 clinical findings into 4 diagnoses. Puzzles live in `puzzles.json` | `python3 -m http.server` then open http://localhost:8000 |
| 4 | [`04-npte-risk-dashboard`](04-npte-risk-dashboard) | Streamlit dashboard: NPTE failure-risk tiers, a cohort heatmap of weak areas, and per-student study plans | `python generate_data.py && streamlit run app.py` |
| 5 | [`05-hibid-lot-evaluator`](05-hibid-lot-evaluator) | CLI: match a lot to sold eBay comps, compute a max bid that targets 3×, and track lots and sales in SQLite with monthly profit | `python make_sample_data.py && python main.py` |

Python projects: `pip install -r requirements.txt` inside each folder first (Python 3.9+).
