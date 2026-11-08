# Knee-wrap BFR intrarater reliability pipeline

Takes raw trial data and produces the reliability numbers you'd report in an abstract:
ICC(3,1) and ICC(3,k) with 95% CIs, SEM, MDC95, and Bland-Altman plots for each pressure condition.

## Quick start

```bash
pip install -r requirements.txt
python generate_data.py   # writes data/synthetic_trials.csv (20 participants x 3 trials x low/high)
python analysis.py        # writes everything to output/
```

### Outputs (`output/`)

| File | What it is |
|---|---|
| `reliability_summary.csv` | One row per condition: ICCs with CIs, F, p, mean, SD, SEM, MDC95 |
| `bland_altman_summary.csv` | Bias, limits of agreement, and a proportional-bias test (slope of difference on mean) for each pair of trials |
| `bland_altman_<condition>.png` | Bland-Altman plots (T1–T2, T1–T3, T2–T3) |
| `results_report.md` | Results paragraph formatted like an APTA abstract, plus a table |

## Methods used

- **ICC(3,1) / ICC(3,k)**: two-way mixed effects, consistency, single and average measures
  (Shrout & Fleiss 1979). 95% CIs use the F-distribution method from McGraw & Wong (1996).
  These match SPSS "Two-Way Mixed, Consistency" and `pingouin.intraclass_corr` ICC(C,1) / ICC(C,k).
- **SEM** = SD × √(1 − ICC(3,1)), where SD is the SD of all observations in that condition.
- **MDC95** = SEM × 1.96 × √2.
- Interpretation labels follow Koo & Li (2016).

If your protocol calls for absolute agreement (ICC(2,1)), change the formula in `icc3()`. The ANOVA
pieces you need (MSR, MSE, and the column sum of squares) are already computed there.

## Swapping in real data

1. Save your data as a CSV with these four columns (long format, one row per trial):

   | participant_id | condition | trial | pressure_mmhg |
   |---|---|---|---|
   | S01 | low | 1 | 72.4 |
   | S01 | low | 2 | 70.9 |
   | ... | ... | ... | ... |

   - `participant_id`: any code. **Use de-identified codes, never names or MRNs.**
   - `condition`: any labels (for example `low`/`high`, `40pct`/`80pct`). Each label is analyzed separately.
   - `trial`: 1, 2, 3, ... Any number of trials works; k is taken from the data.
   - `pressure_mmhg`: the achieved pressure.
2. Run `python analysis.py --input path/to/your_data.csv --outdir output_real`.
3. Participants missing a trial in a condition are dropped from that condition (listwise), and the
   script prints a note when this happens.

If your spreadsheet is wide (one column per trial), convert it in pandas first:
```python
df.melt(id_vars=["participant_id", "condition"], var_name="trial", value_name="pressure_mmhg")
```

> Keep real participant data out of git. `data/*` other than the synthetic file is ignored by `.gitignore`.
