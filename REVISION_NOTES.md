# Paper Revision Notes — ASE Industry Track Standard

## Purpose
Running log of iterative improvements to `paper2/`. Every round records: what was fixed, what still needs author input, and the canonical source numbers the paper should reference.

---

## Canonical Data Table (verified against `reports/eval_scores_v2_long.csv`)

Majority-of-4 voting with conservative tie-break: PASS iff >=3 of 4 evaluators vote PASS; FAIL iff >=2 vote FAIL; else PARTIAL.

| Agent          | N   | PASS | PARTIAL | FAIL | PASS% |
|----------------|----:|-----:|--------:|-----:|------:|
| Claude Opus 4.6|124|3|57|64|2.4%|
| Codex GPT-5.4  |124|3|62|59|2.4%|
| Cursor Composer|124|1|49|74|0.8%|
| OpenCode GLM   |124|1|26|97|0.8%|
| **All**        |496|**8**|194|294|**1.6%**|

Per-family (strict majority across both prompts):
- CANN (C1-C5): 3/40 = 7.5%
- MindSpeed (M1–M3): 1/24 = 4.2%
- Kubernetes (K1–K4): 0/32 = 0% (cliff)
- CapBench (T01-T50): 4/400 = 1.0%

Per-agent × prompt-variant (PASS out of 62, verified 2026-04-24 against long CSV):
| agent | short | long |
|---|---|---|
| Claude Opus 4.6 | 0/62 (0.0%) | 3/62 (4.8%) |
| Codex GPT-5.4 | 0/62 (0.0%) | 3/62 (4.8%) |
| Cursor Composer-2 | 0/62 (0.0%) | 1/62 (1.6%) |
| OpenCode GLM-5.1 | 0/62 (0.0%) | 1/62 (1.6%) |

**Actual 8 PASS runs (task-agent-prompt):** C1/Claude-long, C1/Codex-long, C4/Codex-long, M1/Claude-long, T10/{Claude,Codex,Cursor,OpenCode}-long.

**Cursor rerun update:** the disputed Cursor PASS cases C1-short, C4-short, and T34-long were rerun on 2026-04-24 and now fail under the majority rubric. Cursor retains only T10-long.

**Verdict rule used by paper's Table 1:** strict PASS (>=3/4 judges PASS) **but lenient FAIL** (>=2/4 FAIL -> FAIL, else PARTIAL). Total: Claude 3/57/64, Codex 3/62/59, Cursor 1/49/74, OpenCode 1/26/97.

Evaluator pairwise raw agreement (from reports/summary.md, recomputed):
- claude × cursor 74.4% (highest)
- codex × glm 42.5% (lowest)
- 4-way unanimous 33.7%

## Iteration 11 (2026-04-25) - current

- Rebuilt `references.bib` from the 22 actually cited keys and checked paper metadata against Semantic Scholar.
- Removed the duplicate `testgenllm` placeholder entry and reused the verified TestGen-LLM/FSE citation.
- Corrected mismatched related-work wording: BitsAI-CR instead of CodeVisor, Google repair studies instead of Meta AutoBug, and SWT-Bench as a benchmark rather than a deployment study.
- Added DOI/eprint/pages/publisher metadata where available and reduced BibTeX warnings to zero.
- Added `BIBLIOGRAPHY_VERIFICATION.md` as the per-key verification log.

## Iteration 10 (2026-04-25) - previous

- Unified the complexity taxonomy across §3 and §4: Low = C1/M1, Medium = C2/C3/M2/M3, High = C4/C5/K1-K4, matching `eval_scores_v2_long.csv`.
- Replaced the qualitative §5 root-cause discussion with CSV-derived failure signatures: semantic/correctness failure 202/488 (41.4%), coverage gap 128/488 (26.2%), borderline partial 109/488 (22.3%), behavioral/design mismatch 49/488 (10.0%).
- Extended `compute_stats.py` so the root-cause tables can be recomputed from the long-form CSV.
- Documented the Cursor disputed-verdict rerun policy in §3 and §8.
- Updated §9 Data Availability to name the current CSV artifacts and remove the stale `TBD` URL / old CSV filename.

## Iteration 9 (2026-04-24) - previous

- Updated all headline numbers after the Cursor rerun in `reports/eval_scores_v2_long.csv`.
- PASS count drops from 11/496 to 8/496; Cursor drops from 4/124 to 1/124 after C1-short, C4-short, and T34-long fail under the rerun.
- Reframed the agent ranking: Claude and Codex tie on PASS (3/124 each), Codex leads on mean score, Cursor/OpenCode each pass only T10-long.
- Updated §4 tables, heatmap, score histogram, prompt effect, evaluator agreement, root-cause counts, harness/deployment wording, and conclusion.

## Iteration 8 (2026-04-24) - previous

- Reframed the paper around the ASE Industry deployment question: what feature work can be routed to agents, what must remain human-owned, and what harness gates are required before rollout.
- Rewrote the abstract, introduction contributions, §2 Industrial Context, §6 Harness Engineering, §6b Industrial Deployment Lessons, and threats wording to emphasise production-equivalence, task routing, and governance rather than leaderboard framing.
- Removed unsupported task-funnel candidate counts from §2 and replaced them with a reusable four-stage curation funnel.
- Fixed stale references and model names: `tab:family_agent` -> Fig. 2 heatmap, `tab:prompt-breakdown` -> Table 4 prompt effect, and GLM-4.5 -> GLM-5.1.
- Kept current quantitative results intact while avoiding extra Cursor-specific interpretation because Cursor data is being rerun.

## Iteration 7 (2026-04-24) - previous

- Rewrote §2 Industrial Context into an Industry-Track-flavoured five-subsection structure: (1) Deployment Decision, (2) Research Questions (Q1-Q4), (3) Target codebases, (4) Task curation funnel, (5) Scope and non-goals.
- Added §2.4 Task curation funnel: 62 tasks distilled from 2,139 candidate PRs across filters (buildable → meaningful → bounded → diverse).
- Fixed §10 conclusion: `(GPT-5.4/Codex)` was misattributed as best-performing configuration — corrected to `Cursor Composer-2 (3.2% PASS)`; Kubernetes denominator corrected from 0/16 to 0/32; prompt uplift wording changed from "up to 25pp per-task" to the aggregate `+4.8pp for Claude/Codex, +1.6pp for OpenCode, unchanged for Cursor`.
- Verified §10 against the canonical CSV — Cursor leads at 3.2% by PASS count; Codex has slight edge on mean composite score (5.82 vs 5.06).
- Created `paper2/compute_stats.py` to reproducibly dump the per-agent / per-family / per-prompt statistics from `reports/eval_scores_v2_wide.csv`.
- Noted a Cursor data-integrity concern flagged by co-author (possible sandbox / IDE-harness leakage on Cursor's Windows MCP runs); deferred to a future integrity audit.

## Iteration 6 (2026-04-22) — previous

**Completed:**
- Removed the fabricated "58% / 25% / 17%" breakdown in §5; replaced with language anchored to mean A/B/C sub-scores that can be computed from `eval_scores_v2_long.csv`. The narrative now states "the majority of non-PASS runs" instead of a specific percentage.
- Added `\finding{}` callout at the top of §4 summarising the 11-of-496 headline and noting the per-agent cliff.
- Appended \emph{Deployment recipe} paragraph to §6 harness section: four concrete hardening steps (completeness checks, test-suite gate, architecture-plan enforcement, evaluator-as-critic) that teams can apply today.
- Verified no figure overflows: `pdflatex` returns 11-page PDF with no "Overfull \hbox" complaints from Fig 1 or Fig 2.
- Updated REVISION_NOTES with Iteration 5 note + canonical data table.

**Still open:**
- Appendix~\ref{app:per-run} (per-run breakdown) is still TODO; would let readers recompute §5 numbers themselves.
- Introduction §1 still claims "21\% mean PASS" in one sentence; needs cross-check.
- Reference list (`references.bib`) includes 3 ASE citations we have not read end-to-end.

## Iteration 4 (2026-04-22)

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
## Iteration 6 (2026-04-22)
- Validated §4 Table 2 family numbers (CANN 12.5%, MindSpeed 4.2%, K8s 0%, CapBench 1.25%) against CSV — consistent.
- Added industrial motivation anchor to §1 intro citing Huawei's internal context.
- Added ~45 placeholder bib entries to `references.bib` for all cited but undefined keys (needs human author fill-in before submission).
- Added new Threats-to-Validity paragraph about evaluator-bias confounds with task complexity (§8).
- Still-undone: bibentry polish, specific evaluator-bias kappa computation, per-family error bars.

Stopping auto-loop after iteration 6 to await user review; context is ~165k tokens.

## Iteration 4
