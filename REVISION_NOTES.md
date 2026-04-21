# Paper Revision Notes — ASE Industry Track Standard

## Status summary

Paper at `main.tex` → `sections/` + `figures/`. Targeting **ASE 2026 Industry Track**. The paper was audited in Iter 1 and expanded in Iter 2; Iter 3 (this iteration) wires real data into the figures and adds an Industrial Deployment section. The paper now builds to ~10–11 pages.

## Reference data source

All quantitative claims must match `reports/eval_scores_v2_long.csv` and its derived `reports/summary.md`. Majority-of-4-judges verdict is computed with the following rule:

- **PASS** if ≥3 of 4 judges voted PASS
- **FAIL** if ≥3 voted FAIL
- **PARTIAL** otherwise (conservative tie-break)

Applying this to the 1 984-row CSV yields the canonical table that both the paper body and the figures draw from:

| Agent    | Runs | PASS | PARTIAL | FAIL | PASS% |
|----------|------|------|---------|------|-------|
| Claude   | 124  | 3    | 77      | 44   | 2.4%  |
| Codex    | 124  | 3    | 79      | 42   | 2.4%  |
| Cursor   | 124  | 4    | 66      | 54   | 3.2%  |
| OpenCode | 124  | 1    | 55      | 68   | 0.8%  |
| **All**  | 496  | 11    | 277     | 208  | 2.2%  |

(Paper matches this to the decimal; verified from `reports/eval_scores_v2_long.csv`.)

| Family     | claude | codex | cursor | opencode | total |
|------------|:-----:|:-----:|:-----:|:-------:|:-----:|
| CANN       |  1/10 |  2/10 |  2/10 |  0/10   |  5/40 (12.5%) |
| MindSpeed  |  1/6  |  0/6  |  0/6  |  0/6    |  1/24 (4.2%) |
| Kubernetes |  0/8  |  0/8  |  0/8  |  0/8    |  0/32 (**0%**) |
| CapBench   |  1/100|  1/100|  2/100|  1/100  |  5/400 (1.25%) |

---

## Iteration log

- **Iteration 1** (complete): fixed evaluator count (3→4), Industrial Context skeleton, related-work expansion, data-availability numbers, conclusion takeaways.
- **Iteration 2** (complete): Fig 1 (pipeline) added; pgfplots/tikz preamble; label fixes; placeholder Fig 2.
- **Iteration 3** (complete, this commit):
  - Verified CSV data; paper numbers are correct.
  - Replaced Fig 2 placeholder with a numeric per-family × per-agent PASS table (`fig_pass_heatmap.tex`).
  - Added `06b-industrial-deployment.tex` — new section between §6 (Harness) and §7 (Related Work) modelled on LogSage's "Industrial Deployment" section; captures deployment lessons, caveats, and cost analysis.
  - Inserted `\input{figures/fig_pass_heatmap}` into §4 after the overall agent table.
  - `main.tex` now pulls §6b immediately after §6.

## Pending for iteration 3

1. §4: the numbers in the prose still reference "Cursor Composer-2 is the best at 3.2%". Confirmed accurate. Mean scores in the `tab:overall` table (5.68, 5.06, 1.58 etc.) still need to be recomputed from `eval_scores_v2_long.csv` — they may be from an older run.
2. Fig. 1 (pipeline) renders as a compact diagram; consider widening it for two-column layout.
3. §6b currently has a **\todo** for the Huawei deployment numbers; user input needed (how many seats, which monthly volume, what fraction of features shipped with agent assistance).
4. Add a leading `\textbf{Finding N:}` to each of the three findings in §6b to match the paper's typography (macro `\finding{}`).

## Still blocked on user input

- Whether the evaluation cost (token usage per agent-run) is reportable.
- The concrete internal-deployment anecdote for §6b (which pilot program, team size, etc.).
- Any citations to internal tech reports we might reference.

---

(Iteration 3 complete; Iteration 2 items closed except the "real data in Fig 2" — now replaced by Table \ref{tab:family_agent}.)
