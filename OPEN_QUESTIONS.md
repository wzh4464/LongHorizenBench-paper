# Open Questions for Paper Finalization

Questions only the human author / team can answer. Each question includes where in the paper it appears and why it matters.

---

## Section 2 — Industrial Context

**Q2.1 — Team & deployment scale.**
The scaffolding I wrote is generic ("at our industrial partner"). An ASE-Industry reviewer will ask for concrete numbers: how many engineers do these agents assist? daily active? PRs/week with agent involvement? Please fill in any of the following you can disclose:
- Headcount of the target engineering organization (e.g., "≈X K engineers across the CANN / Kubernetes / MindSpeed teams").
- Daily or weekly agent-assist adoption in production code review or coding.
- Any pilot deployment numbers (e.g., "X PRs/month merged with Codex assistance in 2025").

**Q2.2 — Workflow the benchmark represents.**
Does the benchmark represent:
(a) **Feature PRs** written by a junior engineer + reviewed by senior,
(b) **Bug fixes** driven by an issue tracker,
(c) **Refactoring** initiated internally,
(d) some mix?
This shapes how we frame the failure-mode discussion.

**Q2.3 — Economic stake.**
If possible, one quantified pain-point (e.g., "average 3 engineer-days to land a Kubernetes feature PR; our benchmark targets the 30% of that time spent on mechanical cross-file changes."). This transforms the paper from "academic benchmark" to "industrial diagnosis."

---

## 6 — Harness section

**Q6.1 — Harness results.**
The `A3` (Opus + Loop) configuration exists in the data. Do we have any explicit comparison numbers between A2 (no loop) and A3 (with loop)? The current Harness section cites +1.83pp improvement; is that still current or was it from an earlier run?

**Q6.2 — Harness definition.**
Do we consider the following as harness components: (a) test-execution feedback, (b) repeat-on-fail loops, (c) structured prompt scaffolding, (d) plan-before-code chains? Confirm the scope we claim.

---

## Data availability

**Q-data.1.** Can we release the full 62-task benchmark + evaluation scripts under an OSS license? ASE Industry reviewers expect reproducibility. If Huawei-internal tasks cannot be released, we need to: (a) document that, (b) release the 50 CapBench tasks publicly, (c) provide the 12 Huawei tasks via request-only.

**Q-data.2.** Are the evaluator prompts releasable? The 4-judge ensemble is a core contribution — we should publish the judge prompts and rubric.

---

## Citations / prior-art

**Q-ref.1.** Missing citations I identified during the related-work rewrite (need your confirmation / preferred bibkey):

- FeatBench (feature-level bench): `featbench2024`
- SWE-Bench Verified: `jimenez2024swebench` (already cited)
- Passerine at Google: `mundler2024passerine`
- Confucius (LLM-for-eng): need arXiv link
- Meta WhatsNew / AutoBug: `lou2024whatsnew`

If you have the official .bib entries or PDFs for any of these, drop them in `paper2/references.bib`.

## Stylistic notes from ASE-Industry samples

- Industry Showcase papers average ~12 pages; we're tracking well.
- Use a "What we learned" callout box after each experiment section (LogSage template): reviewers respond well to discrete, quotable lessons.
- Introduce a `\Finding{}` or `\PractitionerTakeaway{}` macro to visually mark each (they do this in ProdCodeBench).

---

## Iteration log
- 2025-01-XX: initial draft of this file; first pass fixed evaluator-count inconsistency and filled Industrial Context skeleton.
