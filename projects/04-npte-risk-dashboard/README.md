# NPTE risk-stratification dashboard

A Streamlit dashboard that sorts DPT students into low, moderate, and high tiers of NPTE failure
risk, shows which content areas the cohort is weak in, and builds a targeted study plan for each
student. It applies a population-risk approach to board prep.

## Run it locally

```bash
cd 04-npte-risk-dashboard
python3 -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python generate_data.py      # creates data/history.csv and data/current.csv (synthetic)
streamlit run app.py         # opens http://localhost:8501
```

Smoke test: `python test_app.py`

## What's on screen

- **Cohort tab:** counts by risk tier, a heatmap of practice-exam % correct by content area
  (students sorted highest risk first), a weak-area summary for the cohort, and a downloadable roster.
- **Student tab:** risk, GPA, PEAT, and hours for one student; their practice-exam scores against
  the cohort mean; and a week-by-week hour allocation with recommendations.
- **Model tab:** cross-validated AUC and odds ratios per SD for each predictor.
- **Sidebar:** upload your own CSVs, drag the tier cutoffs, and set study hours per week and weeks until the exam.

## How the risk score works

Forty students are too few to fit a model on, so the model learns from a **historical cohort**,
past graduates with known first-attempt NPTE results (`history.csv`), and then scores the
**current cohort** (`current.csv`).

- Model: logistic regression on standardized GPA, PEAT score, study hours, and mean practice-exam %.
- Tiers: below 15% predicted failure is Low, 15–35% is Moderate, and 35% or higher is High.
  You can change these in the sidebar.
- Study plan: each content area gets 0.5 h/week of maintenance. The remaining hours are split in
  proportion to *(75% − score) × approximate NPTE weight*, so a big gap in a heavily weighted area
  gets the most time.

The content-area weights in `risk_model.py` (`CONTENT_AREAS`) are **approximate**. Update them
from the current FSBPT NPTE content outline.

## Using real data

Two CSVs, one row per student:

| Column | Notes |
|---|---|
| `student_id` | **Anonymized code only**, never names, emails, or university IDs |
| `gpa` | 0–4 scale |
| `peat_score` | PEAT scaled score |
| `study_hours` | hours logged |
| `pe_musculoskeletal`, `pe_neuromuscular`, `pe_cardiopulmonary`, `pe_integumentary`, `pe_other_systems`, `pe_equipment_modalities`, `pe_safety_professional`, `pe_research_ebp` | practice-exam % correct by area |
| `npte_failed` | **historical file only**: 1 = failed first attempt, 0 = passed |

Upload them in the sidebar, or replace the files in `data/`. `.gitignore` keeps everything in
`data/` except the two synthetic files out of git.

**Caveats:** with a few dozen past failures, the model is a rough screening aid. Check its
calibration against your program's actual outcomes, retrain each year, and use the tiers to start
advising conversations, never to make high-stakes decisions about a student.
