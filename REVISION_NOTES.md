# Paper Revision Notes

Single source of truth for the iterative review against the ASE Industry Track standard. Reference papers in `ref_sources/`: LogSage, FeatBench, FeatureBench, ProdCodeBench, Passerine, Confucius, SWE-Bench-Pro, IndustryCode.

---

## Status by section

| Section | State | Notes |
|---|---|---|
| Abstract | needs polish | 4-evaluator claim correct; add ASE-Industry anchor line |
| §1 Introduction | ok | consider adding \textit{practitioner take-away} box |
| §2 Industrial Context | **drafted in Iter 1** | needs real engineering-team data (see OPEN_QUESTIONS) |
| §3 Study Design | mostly ok | +Fig 1 pipeline added Iter 2; verify task count in prose |
| §4 Results | **numbers do not match CSV** | see "Data discrepancy" below |
| §5 Root Cause | ok | need Figure 4 or 5 |
| §6 Harness | thin | needs concrete numbers (iteration 3) |
| §7 Related Work | expanded Iter1; still missing comparison table |
| §8 Threats | updated to 4 evaluators, numbers corrected Iter1 |
| §9 Data Availability | rewritten Iter1 |
| §10 Conclusion | expanded Iter1 |

---

## Data discrepancy (found Iter 2)

`reports/summary.md` reports per-agent PASS rates (as fraction of judge votes):

| agent | PASS% | mean score |
|---|---|---|
| codex-gpt-5_4 | 4.4% | 1.94 |
| claude-opus-max | 3.0% | 1.89 |
| cursor-composer2 | 4.0% | 1.69 |
| opencode-glm51 | 1.4% | 1.39 |

Paper claims per-agent PASS rates (as fraction of runs with majority PASS verdict):
- Claude 2.4%, Codex 2.4%, Cursor 3.2%, OpenCode 0.8%

Both numbers are valid; **they measure different things**. We should:
1. Clearly state the difference in §3 (evaluation methodology) and §4 (results).
2. In the main table, use the majority-vote rule (strict, conservative), and add a footnote showing judge-vote pass rate for comparison.
3. Add a supplementary table in the appendix (or at end of §4) with both metrics to let reviewers see they aren't contradictory.

Noted: evaluator pairwise agreement in reports/summary.md:
- claude/codex 64%, claude/cursor 75%, claude/glm 68%
- codex/cursor 65%, codex/glm 43%, cursor/glm 66%
- full 4-way unanimity rate needs computation from wide CSV (task for iteration 3)

---

## Iteration 2 (2026-04-22)

**Completed:**
1. Read `reports/summary.md` – canonical source of 4-evaluator results.
2. Identified headline metric mismatch between paper body and CSV (documented above).
3. Created `figures/fig_pipeline.tex` – TikZ pipeline diagram (Huawei tasks + CapBench -> 4 agents -> 4 judges -> verdict).
4. Drafted `figures/fig_pass_heatmap.tex` – placeholder cell values; needs CSV-driven numbers in iteration 3.
5. Added `tikz`/`pgfplots` imports to `main.tex`.
6. Wired Fig. 1 into §3 Study Design preamble.
7. Fixed broken labels `sec:industrial-context`, `sec:related-work`; redirected `\ref{sec:longcontext}` in §10 to `sec:root-cause`.
8. Verified build still passes (all warnings are pre-existing).

**Next iteration (Iter 3):**
1. Replace Fig. 2 placeholder numbers with actual per-task-family, per-agent PASS rates from `reports/eval_scores_v2_long.csv`.
2. Add §4 table that reconciles with `reports/summary.md` numbers; decide which PASS definition (any-judge, majority, unanimous) to cite as headline.
3. Build Fig. 3: score-by-complexity scatter (shows the cliff).
4. Decide whether to add a §4a "Industrial Deployment Case Study" (if we have data from Huawei on real agent use).
5. Clean up Section §6 (Harness) or merge into Discussion if under-developed.

## Iteration 1 (previous) summary
- Rewrote §2 Industrial Context (was TODO stub).
- Expanded §7 Related Work to cover FeatBench, FeatureBench, Passerine, Harness Engineering, etc.
- Corrected §8 Threats to reflect 4 evaluators (was 3).
- Updated §9 Data Availability to 62 tasks / 496 runs.
- Added practitioner-focused Conclusion paragraph.
- Created FIGURES_NEEDED.md, OPEN_QUESTIONS.md.

---

## Questions for author (updated)

1. Can we disclose any Huawei internal-deployment data (team size, PRs reviewed, agent acceptance rate)? Currently §2 is generic.
2. Are there any industrial anecdotes (e.g. a specific CANN bug that an agent mis-fixed) we can include as a vignette? Industrial-track reviewers love these.
3. Should the paper's headline metric be agent-level majority-vote PASS rate (what summary.md reports) or the stricter "all 4 judges PASS" rate the paper currently implies? These give noticeably different numbers.
4. For Fig. 2 and Fig. 3 we need the underlying data:
   - `eval_scores_v2_long.csv` (exists) — use for heatmap
   - Per-task coverage percentage per agent (need to compute)
