# Reference Papers for ASE 2026 Industry Showcase Submission

Papers relevant to our work on evaluating coding agents for enterprise feature implementation tasks, sorted by structural similarity to our paper (highest first).

**Our paper's key themes**: (1) evaluating coding agents on real industrial codebases, (2) multi-agent/multi-config comparison, (3) feature implementation (not just bug fixing), (4) "harness engineering" as improvement direction, (5) enterprise/industrial context.

## Paper List

| # | Title | First Author | Last Author | Venue | Year | arXiv | Similarity | Relevance Note |
|---|-------|-------------|-------------|-------|------|-------|------------|----------------|
| 1 | FeatBench: Towards More Realistic Evaluation of Feature-level Code Generation | Chengran Yang | -- | arXiv (under review) | 2025 | [2509.22237](https://arxiv.org/abs/2509.22237) | 5 | Feature-level code generation benchmark with natural-language-only requirements; directly addresses same task type (feature implementation) as our work |
| 2 | FeatureBench: Benchmarking Agentic Coding for Complex Feature Development | -- | -- | arXiv (under review) | 2026 | [2602.10975](https://arxiv.org/abs/2602.10975) | 5 | End-to-end feature-oriented agentic coding benchmark with execution-based evaluation; even Claude Opus 4.5 achieves only 11% -- shows difficulty of feature tasks |
| 3 | Evaluating Agent-based Program Repair at Google | Josie Resa | Satish Chandra | ICSE 2025 SEIP | 2025 | [2501.07531](https://arxiv.org/abs/2501.07531) | 5 | Evaluates Passerine (SWE-Agent-like) on Google's internal codebase; compares SWE-Bench bugs vs enterprise bugs; highly similar evaluation structure |
| 4 | IndustryCode: A Benchmark for Industry Code Generation | Puyu Zeng | -- | arXiv | 2026 | [2604.02729](https://arxiv.org/abs/2604.02729) | 5 | First multi-domain industrial code generation benchmark (finance, automation, aerospace); 579 sub-problems from 125 industrial challenges across MATLAB/Python/C++ |
| 5 | SWE-Bench Pro: Can AI Agents Solve Long-Horizon Software Engineering Tasks? | Nikhil Deng | -- | arXiv (under review) | 2025 | [2509.16941](https://arxiv.org/abs/2509.16941) | 4 | Enterprise-level benchmark with 1,865 problems from 41 repos including proprietary startup codebases; 70%+ to <25% performance drop from SWE-Bench |
| 6 | ProdCodeBench: A Production-Derived Benchmark for Evaluating AI Coding Agents | Smriti Jha | -- | arXiv (Meta) | 2026 | [2604.01527](https://arxiv.org/abs/2604.01527) | 4 | Benchmark from real production AI coding assistant sessions at Meta; verbatim prompts + committed code changes + fail-to-pass tests |
| 7 | Building Effective AI Coding Agents for the Terminal: Scaffolding, Harness, Context Engineering, and Lessons Learned | Nghi D. Q. Bui | -- | arXiv | 2026 | [2603.05344](https://arxiv.org/abs/2603.05344) | 4 | Defines scaffolding vs harness for coding agents; directly relevant to our "harness engineering" improvement direction; presents OPENDEV agent |
| 8 | Confucius Code Agent: Scalable Agent Scaffolding for Real-World Codebases | -- | -- | arXiv | 2025 | [2512.10398](https://arxiv.org/abs/2512.10398) | 4 | Industrial-scale agent scaffolding with context management and tool extensions; achieves 54.3% on SWE-Bench via scaffolding alone (not model changes) |
| 9 | Automated Unit Test Improvement using Large Language Models at Meta | Nadia Alshahwan | Mark Harman | FSE 2024 Industry | 2024 | [2402.09171](https://arxiv.org/abs/2402.09171) | 4 | First industrial-scale LLM code deployment report; TestGen-LLM at Meta with 73% acceptance rate; filter-based validation harness for LLM outputs |
| 10 | WhatsCode: Large-Scale GenAI Deployment for Developer Efficiency at WhatsApp | -- | -- | ICSE 2026 SEIP | 2026 | [2512.05314](https://arxiv.org/abs/2512.05314) | 4 | 25-month longitudinal study of domain-specific AI coding tool at enterprise scale; agentless to agentic evolution; 3,000+ accepted code changes |
| 11 | LogSage: An LLM-Based Framework for CI/CD Failure Detection and Remediation with Industrial Validation | -- | -- | ASE 2025 Industry Showcase | 2025 | [2506.03691](https://arxiv.org/abs/2506.03691) | 3 | ASE Industry Showcase paper with industrial validation at ByteDance (1.07M executions); LLM + RAG for CI/CD; demonstrates industry deployment |
| 12 | SWE-EVO: Benchmarking Coding Agents in Long-Horizon Software Evolution Scenarios | -- | -- | arXiv (under review) | 2025 | [2512.18470](https://arxiv.org/abs/2512.18470) | 3 | Long-horizon evolution benchmark (48 tasks, avg 21 files); GPT-5 achieves only 21% vs 65% on SWE-Bench; proposes Fix Rate metric for partial progress |
| 13 | Agentic Bug Reproduction for Effective Automated Program Repair at Google | Runxiang Cheng | Satish Chandra | ICSE 2025 SEIP | 2025 | [2502.01821](https://arxiv.org/abs/2502.01821) | 3 | Agent-based BRT generation + APR at Google; 30% more bugs with plausible fixes; companion to Passerine paper above |
| 14 | Exploring LLM-based Agents for Root Cause Analysis | Devjeet Roy | Rodrigo Fonseca | FSE 2024 Industry | 2024 | [2403.04123](https://arxiv.org/abs/2403.04123) | 3 | ReAct agent with retrieval tools on production incidents at large IT corporation; characterizes success/failure modes of LLM agents in enterprise |
| 15 | LLM-Based Repair of C++ Implicit Data Loss Compiler Warnings: An Industrial Case Study | -- | -- | arXiv (SAP) | 2026 | [2601.14936](https://arxiv.org/abs/2601.14936) | 3 | Industrial case study at SAP HANA (36M LoC C++); 92.73% acceptance rate; LSP + Tree-sitter context for LLM; relevant as C++ industrial evaluation |
| 16 | Examining the Use and Impact of an AI Code Assistant on Developer Productivity and Experience in the Enterprise | Alexander Goldberg | -- | CHI 2025 Extended Abstracts | 2025 | [2412.06603](https://arxiv.org/abs/2412.06603) | 3 | IBM watsonx Code Assistant evaluation (N=669 surveys); characterizes impact of LLM assistant on developer productivity in enterprise |
| 17 | Experience with GitHub Copilot for Developer Productivity at Zoominfo | -- | -- | arXiv | 2025 | [2501.13282](https://arxiv.org/abs/2501.13282) | 3 | Enterprise deployment study of Copilot (400+ developers); 33% acceptance rate; systematic four-phase evaluation; language-specific analysis |
| 18 | Defects4C: Benchmarking Large Language Model Repair Capability with C/C++ Bugs | -- | Yi Li | ASE 2025 Research | 2025 | [2510.11059](https://arxiv.org/abs/2510.11059) | 3 | C/C++ repair benchmark (248 buggy functions); evaluates 24 LLMs; relevant as benchmark for C/C++ code (similar to our CANN/C++ tasks) |
| 19 | Agentless: Demystifying LLM-based Software Engineering Agents | Chunqiu Steven Xia | Lingming Zhang | arXiv / ICSE 2025 | 2024 | [2407.01489](https://arxiv.org/abs/2407.01489) | 3 | Influential baseline showing simple 3-phase approach (localize, repair, validate) beats complex agents; relevant to our harness engineering thesis |
| 20 | CodeVisionary: An Agent-based Evaluation Framework for Complex Code Generation | Xinchen Wang | Cuiyun Gao | ASE 2025 Research | 2025 | [2504.13472](https://arxiv.org/abs/2504.13472) | 3 | Agent-based evaluation framework with multi-dimensional scoring and explainability; 363 samples, 37 scenarios, 23 languages |

## Summary Statistics

- **ASE Industry Showcase**: 1 paper (#11 LogSage)
- **ASE Research**: 2 papers (#18 Defects4C, #20 CodeVisionary)
- **ICSE SEIP**: 3 papers (#3 Passerine@Google, #10 WhatsCode, #13 BRT@Google)
- **FSE Industry**: 2 papers (#9 TestGen-LLM@Meta, #14 RCA agents)
- **Other venues/arXiv preprints**: 12 papers

- **With arXiv preprint**: 20/20 (100%)
- **Industrial evaluation (real enterprise codebase)**: 10 papers (#3, #4, #6, #9, #10, #11, #13, #14, #15, #17)
- **Coding agent benchmark**: 8 papers (#1, #2, #4, #5, #6, #12, #18, #20)
- **Harness/scaffolding engineering**: 3 papers (#7, #8, #19)

## Similarity Score Legend

| Score | Meaning |
|-------|---------|
| 5 | Very similar: evaluates AI coding tools on real/industrial feature implementation with benchmark |
| 4 | Similar: evaluates coding agents/tools in enterprise or proposes industrial benchmark with agent comparison |
| 3 | Related: addresses coding agent evaluation, industrial deployment, or LLM code generation benchmarks |

## Notes

- ASE 2025 Industry Showcase accepted papers list is not yet fully public (conference in Nov 2025 Seoul); LogSage is one confirmed paper.
- ASE 2024 Industry Showcase specific paper list was not obtainable from web search; the track existed but individual LLM-focused papers were not indexed.
- Several highly relevant papers (#1, #2, #5, #7, #8, #12) are arXiv preprints that may be under review at top SE venues.
- Papers #3 and #13 (both from Google) form a complementary pair on agent-based program repair.
- Paper #7 (Building Effective AI Coding Agents) is the most directly relevant to our "harness engineering" concept, explicitly defining the term.

---
*Generated 2026-04-06 for ASE 2026 Industry Showcase submission on coding agent evaluation.*
