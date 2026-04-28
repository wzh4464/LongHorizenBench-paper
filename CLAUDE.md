# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LaTeX manuscript for an ASE 2026 Industry Showcase paper. The paper evaluates whether LLM-based coding agents can produce merge-ready feature PRs, using a 62-task benchmark across industrial (Huawei CANN, MindSpeed, torch_npu) and open-source (Kubernetes, Kafka, CPython, etc.) codebases. This repo is a git submodule of the parent benchmark repository at `../`.

**Venue**: ASE '26 Industry Showcase, ACM sigconf format, 10+2 pages.

## Build Commands

```bash
# Full build (LaTeX + BibTeX)
pdflatex main && bibtex main && pdflatex main && pdflatex main

# Quick rebuild (no bib changes)
pdflatex main

# Recompute headline statistics from evaluator CSV
python3 compute_stats.py                              # auto-finds ../reports/eval_scores_v2_long.csv
python3 compute_stats.py path/to/eval_scores_v2_long.csv  # explicit path
```

## Manuscript Structure

`main.tex` includes sections in order:

| File | Section | Content |
|------|---------|---------|
| `sections/abstract.tex` | Abstract | |
| `sections/01-introduction.tex` | §1 Introduction | Motivation + contributions |
| `sections/03-study-design.tex` | §3 Study Design | Task registry, agent configs, scoring rubric |
| `sections/04-results.tex` | §4 Results | RQ1–RQ2 findings, tables |
| `sections/05-root-cause.tex` | §5 Root Cause | Failure signature breakdown |
| `sections/06b-industrial-deployment.tex` | §6 Deployment | Policy gates, industrial guidance |
| `sections/07-related-work.tex` | §7 Related Work | |
| `sections/08-threats.tex` | §8 Threats | |
| `sections/10-conclusion.tex` | §10 Conclusion | |
| `sections/09-data-availability.tex` | Data Availability | Unnumbered, after conclusion |

Commented-out sections: `02-industrial-context.tex` (merged into §1), `06-harness.tex` (consolidated into §6b).

## Figures

- `figures/fig_pipeline.tex` — TikZ evaluation pipeline diagram
- `figures/fig_pass_heatmap.tex` — TikZ PASS-rate heatmap (agent × task family)
- `figures/fig_score_hist.tex` — TikZ score distribution histogram
- `figures/src/score_dist.json` — data backing the histogram

All figures are TikZ (no external image files). Edit the `.tex` files directly.

## Canonical Data

The single source of truth for all numbers in the paper is `../reports/eval_scores_v2_long.csv`. Key aggregates:

- **496 runs** total: 62 tasks × 4 agents × 2 prompts
- **Overall PASS rate**: 8/496 = 1.6% (strict majority-of-4 voting)
- **Verdict rule**: PASS = ≥3/4 judges PASS; FAIL = ≥2/4 judges FAIL; else PARTIAL
- All 8 PASS runs are long-prompt: C1/Claude, C1/Codex, C4/Codex, M1/Claude, T10/{all 4 agents}

`compute_stats.py` regenerates headline numbers, per-agent tables, per-family breakdowns, and root-cause failure signatures from this CSV. Always re-run it after CSV changes rather than hand-editing numbers in `.tex` files.

## Key Documents in This Directory

- `WRITING_CONTEXT.md` — experiment matrix, RQs, task complexity table, key results summary
- `REVISION_NOTES.md` — iteration log with canonical data table and per-round changes
- `OPEN_QUESTIONS.md` — unresolved questions requiring human author decisions
- `FIGURES_NEEDED.md` — figure specs (what exists, what's needed, data sources)
- `BIBLIOGRAPHY_VERIFICATION.md` — per-citation-key verification log against Semantic Scholar
- `pro_plan.txt` — current revision/submission plan
- `paper.txt` — plain-text export of current manuscript

## Writing Conventions

- Use the `\finding{}` macro for key findings (defined in `main.tex` preamble).
- All numbers must trace to the CSV via `compute_stats.py`. Never approximate or round data.
- BibTeX keys are verified in `BIBLIOGRAPHY_VERIFICATION.md`; check there before adding new citations.
- `references.bib` contains exactly the cited keys (currently 22). Do not add unused entries.
- Write in English. Academic tone targeting industrial practitioners.

## Scoring Terminology

The paper uses a strict-equivalence scoring rubric:
- Three dimensions (0–5): **A** Functional Correctness, **B** Completeness & Coverage, **C** Behavioral Equivalence
- PASS = A≥4 AND B≥4 AND C≥3 (strict)
- FAIL = A≤1 OR destructive
- PARTIAL = everything else
- Majority-of-4 voting with conservative tie-break across 4 LLM evaluators

## Parent Repository

The benchmark infrastructure lives in `../` (parent repo). Key paths referenced by this manuscript:
- `../reports/eval_scores_v2_long.csv` — the canonical evaluation CSV
- `../experiment/` — per-run experiment directories and evaluation results
- `../base_repo/` — 62 task definitions with ground-truth diffs
