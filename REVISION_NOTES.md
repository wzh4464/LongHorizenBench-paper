# Paper Revision Notes — ASE Industry Track Standard

## Purpose
Running log of iterative improvements to `paper2/`. Every round records: what was fixed, what still needs author input, and the canonical source numbers the paper should reference.

---

## Canonical Data Table (verified against `reports/eval_scores_v2_long.csv`)

Majority-of-4 voting, strict: PASS iff ≥3 of 4 evaluators vote PASS; FAIL iff ≥3 vote FAIL; else PARTIAL.

| Agent          | N   | PASS | PARTIAL | FAIL | PASS% |
|----------------|----:|-----:|--------:|-----:|------:|
| Claude Opus 4.6|124|3|91|30|2.4%|
| Codex GPT-5.4  |124|3|?|?|2.4%|
| Cursor Composer|124|4|66|54|3.2%|
| OpenCode GLM   |124|1|55|68|0.8%|
| **All**        |496|**11**|—|—|**2.2%**|

Per-family (strict majority across both prompts):
- CANN (C1–C5): 5/40 = 12.5%
- MindSpeed (M1–M3): 1/24 = 4.2%
- Kubernetes (K1–K4): 0/32 = 0% (cliff)
- CapBench (T01–T50): 5/400 = 1.25%

Per-agent × prompt-variant (PASS out of 62):
| agent | short | long |
|---|---|---|
| claude | 1 (1.6%) | 2 (3.2%) |
| codex  | 0 (0.0%) | 3 (4.8%) |
| cursor | 2 (3.2%) | 2 (3.2%) |
| opencode | 0 (0.0%) | 1 (1.6%) |

Evaluator pairwise raw agreement (from reports/summary.md, recomputed):
- claude × cursor 74.8% (highest)
- codex × glm 42.7% (lowest)
- 4-way unanimous 41.3%

## Iteration 4 (2026-04-22) — current

- Re-verified per-agent PASS rates against `reports/eval_scores_v2_long.csv` using strict majority-of-4. Numbers in §4 match.
- Replaced Fig. 2 heatmap stub with a real pgfplots matrix plot driven by per (family, agent) PASS%.
- Added a legend to Fig. 1 (pipeline diagram): agent / judge / verdict.
- §5 root-cause: the 58% / 25% / 17% buckets are still analyst estimates; flagged for later replacement with CSV-derived percentages.

## Iteration 3 (previous)

- Created `sections/06b-industrial-deployment.tex` (Industrial Deployment Lessons section).
- Added Fig 1 (pipeline), Fig 2 (heatmap table) references in §4.
- Updated preamble of `main.tex` to load `tikz`, `pgfplots`, `colortbl`.
- Added `figures/` subdirectory.

## Iteration 2 (previous)

- Fixed "3 evaluators" to "4 evaluators" throughout; rewrote §8 Threats.
- Fixed label mismatches: `sec:industrial-context` / `sec:related-work`.
- Updated §9 Data Availability to 62 tasks / 496 runs / 4 evaluators.
- Expanded §10 Conclusion with Implications-for-Practice and Research-Agenda.

## Iteration 1 (previous)

- Diagnosed gaps: §2 was a stub; §7 referenced non-existent papers; §8 described 3 judges.
- Created `REVISION_NOTES.md`, `FIGURES_NEEDED.md`, `OPEN_QUESTIONS.md`.
- Rewrote §2 Industrial Context as a scoped introduction.
- Expanded §7 Related Work with 4 prior-benchmark categories.