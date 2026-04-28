# Bibliography Verification Log

Date: 2026-04-25

Scope: all 22 citation keys used by `main.tex` and `sections/*.tex`.
Primary metadata source: Semantic Scholar API using the local `.env` key.
Release/blog pages were checked as release pages rather than scholarly papers.

| Citation key | Verification result | Action taken |
|---|---|---|
| `github2024survey` | GitHub Octoverse 2024 release page. | Kept as `@misc` with URL. |
| `jimenez2024swebench` | Semantic Scholar matched SWE-bench / ICLR 2024 / arXiv:2310.06770. | Added OpenReview publisher, arXiv metadata, and PDF page count. |
| `chowdhury2024swebenchverified` | OpenAI SWE-bench Verified release page. | Kept as `@misc` with URL. |
| `swebenchpro2025` | Semantic Scholar matched arXiv:2509.16941. | Filled complete author list, DOI, eprint, URL. |
| `swebenchlive` | Semantic Scholar matched arXiv:2505.23419. | Filled author list, DOI, eprint, URL. |
| `multiswebench` | Semantic Scholar matched arXiv:2504.02605. | Filled author list, DOI, eprint, URL. |
| `tddbench` | Semantic Scholar matched arXiv:2505.09027. | Converted to arXiv `@misc` with DOI/eprint. |
| `featbench2025` | Semantic Scholar matched "FeatBench: Evaluating Coding Agents on Feature Implementation for Vibe Coding" / DOI 10.48550/arXiv.2509.22237. | Corrected title and authors; added DOI/eprint/URL. |
| `sweevo` | Semantic Scholar matched arXiv:2512.18470. | Corrected stale arXiv id and author list. |
| `crbench` | Semantic Scholar matched arXiv:2509.14856. | Corrected full title and author list. |
| `mathai2024passerine` | Semantic Scholar and DOI matched ICSE-SEIP 2025 paper "Evaluating Agent-Based Program Repair at Google". | Converted to published `@inproceedings` with DOI/pages/publisher. |
| `prodcodebench2024` | Semantic Scholar matched ProdCodeBench arXiv:2604.01527, year 2026. | Corrected title and year; kept existing key for citation stability. |
| `alshahwan2024testgen` | DOI 10.1145/3663529.3663839 matched FSE Companion 2024 TestGen-LLM paper. | Added DOI/pages/publisher/eprint. |
| `multiagent2024` | Semantic Scholar matched CodeR arXiv:2406.01304. | Filled author list, DOI, eprint, URL. |
| `harness2025` | DOI 10.52202/079017-1601 matched SWE-agent NeurIPS 2024. | Converted to published `@inproceedings` with DOI/pages. |
| `agentless` | DOI 10.1145/3715754 matched PACMSE/FSE 2025 article. | Converted from arXiv placeholder to journal article. |
| `confucius` | Semantic Scholar matched Confucius Code Agent arXiv:2512.10398. | Corrected title and author list. |
| `logsage` | DOI 10.1109/ASE63991.2025.00310 matched ASE 2025 LogSage. | Converted to published `@inproceedings` with DOI/pages. |
| `mundler2024passerine` | DOI 10.52202/079017-2601 matched SWT-Bench NeurIPS 2024. | Corrected author order and added DOI/pages. |
| `autobug` | Semantic Scholar matched Agentic Bug Reproduction at Google / arXiv:2502.01821. | Corrected author list and related-work wording. |
| `codevisor` | Semantic Scholar query for CodeVisor resolved to BitsAI-CR / DOI 10.1145/3696630.3728552. | Kept citation key but corrected title/authors and paper wording to BitsAI-CR. |
| `repofusion` | Semantic Scholar matched RepoFusion arXiv:2306.10998. | Added DOI/eprint/URL. |

Removed duplicate/stale key: `testgenllm`.
The paper now cites `alshahwan2024testgen` for TestGen-LLM in both related-work locations.
