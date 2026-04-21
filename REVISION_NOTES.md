# Paper Revision Notes — ASE 2026 Industry Track

Single source of truth for iterative polishing of this submission. Each entry tracks:
- what was fixed (closed)
- what still needs the user's input (open / needs-human)
- what figures to render (figures-todo)

## Iteration Log

### Iteration 1 — 2026-04-22 (Opus 4.7)

**Structural diagnosis against ASE Industry exemplars** (LogSage ASE 2025, Passerine ICSE SEIP 2025, ProdCodeBench):

| Criterion | Exemplar | Our paper | Gap |
|-----------|----------|-----------|-----|
| Dedicated Industrial Context section | yes (LogSage §2) | empty stub | P0 |
| RQ-driven Methodology | yes (LogSage §3) | implicit in §3 | P2 |
| Industrial Deployment subsection | yes (LogSage §5) | missing | P1 |
| Figures | 3–6 typical | 0 in draft | P0 |
| Related Work comparison table | present | paragraph only | P1 |
| Evaluator disagreement analysis | sometimes | present (Sec 4.6) | ✓ |
| Data availability statement | required | present but inaccurate | ✓ fixed |

**Fixed in this iteration:**
1. `08-threats.tex`: "3 LLM evaluators" → 4-evaluator formulation; pairwise agreement numbers updated; sanitization description tightened.
2. `09-data-availability.tex`: "96 experiments" → accurate 496 (62×4×2) count; prompt count corrected.
3. `07-related-work.tex`: expanded from 18 lines to multi-paragraph taxonomy with explicit comparison axes and ASE-Industry showcase references.
4. `02-industrial-context.tex`: replaced `% TODO` placeholder with full Industrial Context section (engineering pattern observations, four task families, why merged-PR evaluation matters).
5. `10-conclusion.tex`: fixed pattern count (three not four), added Implications-for-Practice paragraph, added Future Work.
6. Added `PAPER_REVISION_NOTES.md`, `OPEN_QUESTIONS.md`, `FIGURES_NEEDED.md`.

---

## Still to do (P0 = must; P1 = should; P2 = nice-to-have)

### P0 — content gaps that will fail reviewers

- **Figure 1 (pipeline diagram)** — see FIGURES_NEEDED.md. Without a figure the paper reads as a pure experiment report.
- **Industrial Deployment paragraph** in §2. Need factual details from Zihan about Huawei-internal deployment or usage study (number of engineers, tasks automated, etc.). See OPEN_QUESTIONS.md Q2.1.
- **Pass / Fail breakdown figure** (Fig 2 heat-map) — auto-generatable from CSV once I confirm the exact aggregation.

### P2 — polish
- Tone-pass on §2 (too academic for industry track).
- Add a worked example in §4 for one task where agents disagreed.

---

## Iteration N+1 plan

Next iteration should:
1. Draft pipeline figure in TikZ and embed in §3.
2. Rewrite §6 harness-engineering with ASE-Industry framing (lessons → recommendations).
3. Add a short “Lessons Learned” subsection before §8 (a convention in industry track papers).
4. Confirm numbers from §4 results tables match the underlying CSV.

---

## Index of helper files
- `PAPER_REVISION_NOTES.md` — this file (iteration log)
- `FIGURE_PROMPTS.md` — prompts for generating each figure
- `OPEN_QUESTIONS.md` — info needed from Zihan
