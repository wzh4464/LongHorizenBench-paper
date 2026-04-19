# Paper Writing Context

## Paper Info
- **Venue**: ASE 2026 Industry Showcase (long paper 10+2 pages)
- **Title**: "Not Ready Yet: An Industrial Assessment of Coding Agents for Feature Implementation and the Promise of Harness Engineering"
- **Thesis**: Current coding agents cannot independently complete enterprise-level feature implementation, but Harness Engineering is an effective engineering direction to bridge the gap.
- **Format**: ACM sigconf, LaTeX

## Key Data Files
- `/Users/zihanwu/Public/codes/huawei-eval/experiment/all_scores.csv` — 115 rows, all experiments
- `/Users/zihanwu/Public/codes/huawei-eval/experiment/cross_config_analysis.md` — full cross-config comparison
- `/Users/zihanwu/Public/codes/huawei-eval/experiment/minimax_analysis.md` — minimax deep analysis
- `/Users/zihanwu/Public/codes/huawei-eval/experiment/trajectory_comparison_K4.md` — codex vs claude trajectory
- `/Users/zihanwu/Public/codes/huawei-eval/research_request.md` — full paper plan, RQs, structure

## Experiment Matrix
- **12 tasks**: C1-C5 (CANN, C++), M1-M3 (MindSpeed, Python), K1-K4 (Kubernetes, Go)
- **5 main configs**: A1 (Sonnet), A2 (Opus baseline), A3 (Opus+Loops harness), Codex (gpt-5.4), MiniMax (M2.5)
- **2 prompt types**: long (detailed spec), short (summary only)

## Task Complexity
| ID | Repo | Complexity | Lang | GT Files | GT Lines |
|----|------|-----------|------|----------|----------|
| C1 | cann-ops-adv | Low | C++ | 1 | 6 |
| C2 | cann-ops | Low | C++ | 4 | 33 |
| C3 | torch_npu | Medium | Python | 9 | 782 |
| C4 | cann-ops | Medium | C++/AscendC | 24 | 1273 |
| C5 | cann-ops | High | C++/AscendC | 27 | 3372 |
| M1 | MindSpeed | Low | Python | 3 | 27 |
| M2 | MindSpeed | Medium | Python | 6 | 151 |
| M3 | MindSpeed | High | Python | 10 | 1228 |
| K1 | kubernetes | Low | Go | 13 | 1064 |
| K2 | kubernetes | Medium | Go | 35 | 3873 |
| K3 | kubernetes | Medium | Go | 49 | 11107 |
| K4 | kubernetes | High | Go | 98 | 6794 |

## Key Results (for reference)
- **Overall PASS rate**: ~20% across 115 experiments
- **Codex gpt-5.4**: 41% PASS (best), 64% on long prompts
- **A1 Sonnet**: 35% PASS (20 experiments)
- **A3 Opus+Loops**: 13% PASS, but 0 FAIL (harness prevents catastrophic failure)
- **A2 Opus baseline**: 9% PASS
- **MiniMax M2.5**: 0% PASS
- **Prompt effect**: Long prompts +11-45pp across all configs
- **Harness effect**: A3 wins 12/18 vs A2, mean +1.83 composite
- **Key trajectory finding**: gpt-5.4 uses web search + git archaeology, Claude does not

## RQs
- RQ1: Can current agents independently complete enterprise feature implementation?
- RQ2: What are the root causes of failure? Model capability vs engineering problems?
- RQ3: How effective is Harness Engineering? What are its limits?
- RQ4: Under what conditions is agent-assisted feature implementation worthwhile?

## Writing Style
- Academic but with industrial practitioner audience in mind
- Use actual numbers from CSV, not approximations
- Tables preferred over prose for data presentation
- Each section should be self-contained with clear takeaways
- Use \finding{} macro for key findings (define in preamble)
- Write in English
