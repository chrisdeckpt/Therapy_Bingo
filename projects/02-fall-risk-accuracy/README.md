# Fall-risk screen accuracy comparison

Compares a new, sensitivity-first fall-risk screen against the Berg Balance Scale, Tinetti POMA, and SPPB
for predicting falls over 12 months.

## Quick start

```bash
pip install -r requirements.txt
python generate_data.py   # data/synthetic_cohort.csv: 300 PACE-like older adults
python analysis.py        # output/results.csv, output/roc_curves.png, output/report.html
```

Open `output/report.html` in a browser. It is a single self-contained page with the ROC plot embedded.

## What it computes (per tool)

| Metric | Notes |
|---|---|
| Sensitivity, specificity, PPV, NPV, LR+, LR− | At the published cutoff in the `TOOLS` dict at the top of `analysis.py` |
| AUC (95% CI) | CI from 1,000 bootstrap resamples |
| Sensitivity-first cutoff | Every observed score is tried. It picks the cutoff with the highest sensitivity among those with specificity ≥ 0.50 (ties go to higher specificity). Change the floor with `--min-spec 0.6`. |

## Cutoffs: check these

The defaults are common values from the literature, but published cutoffs vary by population and
study. Confirm them against the papers you plan to cite, then edit `TOOLS` in `analysis.py`:

| Tool | Default | Direction |
|---|---|---|
| New tool | ≥ 8 (placeholder) | higher = more risk |
| Berg | ≤ 45 / 56 | lower = more risk |
| Tinetti POMA | ≤ 18 / 28 | lower = more risk |
| SPPB | ≤ 9 / 12 | lower = more risk |

`risk_if` tells the script which side of the cutoff counts as a positive screen. Scores that run
the other way are flipped automatically for ROC/AUC.

## Using real data

Provide a CSV with one row per person and these columns: `new_tool`, `berg`, `tinetti`, `sppb`,
`fell_12mo` (1 = fell, 0 = did not fall). Other columns, such as `subject_id`, `age`, and `sex`,
are ignored. Rows missing any of these are dropped.

```bash
python analysis.py --input data/real_cohort.csv --outdir output_real
```

Use de-identified IDs only. `.gitignore` excludes everything in `data/` except the synthetic file.

## About the synthetic data

All four tools are noisy readings of one hidden "fall propensity" score, so the results only show
that the pipeline works. **They say nothing about how the real tools compare.** The new tool was
given slightly less noise on purpose.
