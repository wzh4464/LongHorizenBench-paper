# Figures to Generate

Each entry lists: where it goes in the paper, a one-sentence purpose, the data source, and a generation prompt suitable for TikZ, matplotlib, or a design tool.

---

## P0 — Blocking figures

### Fig. 1 — System overview (goes into §2 Industrial Context)

- **Purpose.** Show the end-to-end evaluation pipeline: 62 tasks → 4 agents × 2 prompts → 4 evaluator LLMs → majority-voted verdict.
- **Data source.** None (conceptual diagram).
- **Prompt.**
  > Draw a left-to-right pipeline diagram in TikZ. Left column: a stack of 3 boxes labelled "Huawei CANN (C1–C5)", "MindSpeed / torch_npu (M1–M3, C?)", "Kubernetes (K1–K4)", and a fourth box "CapBench (50 OSS tasks)". Arrow pointing to a box labelled "Prompt Generator (Long / Short variants)". From there, 4 parallel arrows to 4 agent boxes: "Claude Opus 4.6", "Codex GPT-5.4", "Cursor Composer-2", "OpenCode GLM-5.1". Each agent box outputs a diff, which feeds into a vertical stack of 4 LLM-judge boxes ("Claude / Codex / Cursor / GLM as judges"). Final arrow to a voting box "Majority verdict (3-tier, conservative tie-break)" → "PASS / PARTIAL / FAIL". Caption: "Evaluation pipeline: 62 tasks × 4 agents × 2 prompts = 496 runs, each independently judged by 4 evaluators."

### Figure 2 — PASS-rate heat-map

- **File**: `figs/heatmap_pass_by_family.tex`
- **Purpose**: Makes the "Kubernetes family = 0% pass" + "complexity cliff" findings visually undeniable.
- **Shape**: rows = 6 task families (C-low, C-high, M, K, T-easy, T-hard). cols = 4 agents. Cell = PASS%.
- **Data**: derived from `eval_scores_4evaluators.csv`. Need: per (agent, task) pass/fail, then aggregate.
- **Alt text** / caption: "Heat-map of PASS rate (per agent × task family). Darker = fewer wins. Every Kubernetes row is zero."
- **Generation prompt**:
    "Make a 6×4 heat-map with the seaborn.heatmap API. Rows labeled `CANN-C / MindSpeed-M / K8s-K / CapBench-easy / CapBench-med / CapBench-hard`; columns labeled with the four agent short names. Cell colour = pass rate. Annotate each cell with `pass/total`. Use a single-hue greyscale to avoid redundant encoding."

### Figure 3 - Prompt effect slope-chart
- **What it shows**: per-agent improvement from short-prompt → long-prompt. Delta drives the Harness Engineering chapter.
- **Data**: Table II in `sections/04-results.tex` has the raw numbers; need the short vs long PASS% for each of the four agents.
- **Layout**: left axis short-prompt pass %, right axis long-prompt pass %, four coloured slopes (one per agent).
- **Generation prompt**: "Produce a slope-chart with matplotlib: four coloured slopes, one per agent. x in {short, long}, y = pass rate (%). Annotate each slope endpoint with the agent name + value."

### Figure 4 - Failure-cause stacked bars
- **What it shows**: failure decomposition per agent (incomplete coverage / wrong API / test omission / hallucination / other).
- **Input**: need you to confirm or collect the per-experiment failure tags used in the error-analysis table at the end of §4. Without those we can only produce a stub.

## Figures already covered by existing tables
- The table at Study Design (config matrix) and the results tables in §4 are sufficient. No extra figures needed for those.

## What we still need from the human

1. **Per-experiment failure-cause labels** for Figure 4 (categorical: one of {partial, wrong_api, no_tests, hallucination, other}). If not available, Figure 4 stub will use aggregate counts only.
2. **Confirm Kubernetes PASS rate = 0** for both prompt variants (current draft assumes this; need a final sweep after the most recent K3/K4 runs).
3. **Per-task handwritten-file counts** for Table~`\ref{tab:complexity-capbench}` (the CapBench complexity table). We have totals per family but not per row.
