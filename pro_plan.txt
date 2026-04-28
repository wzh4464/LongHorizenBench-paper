# ASE 修稿计划（仅包含**不需要新增实验**的修改）

> 适用范围：只做写作重构、现有数据重分析、图表/术语/引用清理、已有日志提取。
> 不包含：online pilot、主语料新的人评 acceptability、任何新增 run。

---

## 0. 范围冻结（先明确哪些**不在这版 plan**里）

- [ ] **不做** online rollout / pilot funnel（需要新增线上数据）
- [ ] **不做** main corpus 的 RA-PASS / reviewer-acceptable 新人评（需要新增实验）
- [ ] **不做** main corpus 的新一轮 human re-rating / stratified sample（需要新增实验）
- [ ] **保留并前置**已有的 C/K/M calibration 人评证据：12 个 C/K/M 任务、96 runs、3 位 blinded senior reviewers、92.7% SE-PASS-vs-non-SE-PASS agreement；把它当作**现有校准器**，不是 future work

---

## 1. 叙事改造：从“benchmark/report paper”改成“deployment decision paper”

### 1.1 重写标题下的主叙事
- [ ] 将全篇主线改成：**industrial deployment question → audit protocol → capability boundary → four-gate policy → current rollout rule**
- [ ] Abstract 第一段只保留 deployment decision，不再把 benchmark setup 写成最先出现的信息
- [ ] Introduction 前半段减少 leaderboard/benchmark 背景，强化“2026 年 Huawei 多个平台团队要决定 agent-first 是否可上线”
- [ ] 将“为什么现有 benchmark 不回答这个问题”压缩成 1 段，不要重复多次

### 1.2 收紧贡献表述
- [ ] Contributions 压成 **3 条**：
  - deployment policy
  - audit evidence base
  - anti-leakage + calibrated evaluation protocol
- [ ] 将“primary contribution / clear answer / not a benchmark question”这类重复句式删减，避免在 Abstract、Intro、Conclusion、§5 反复出现
- [ ] 所有“绝对化”表述降一档，例如：
  - `categorically out of reach` → `under our protocol, we observed 0/32`
  - `clear answer` → `the audit supports the following deployment decision`

### 1.3 结构重排
- [ ] 把 §5 从“lessons learned”写法，改成**正文主结果落点**（例如：`Deployment Policy Derived from the Audit`）
- [ ] Figure 5（deployment pipeline）前移到更靠前的位置，最好在 Results 尾部或进入 §5 开头时立即出现
- [ ] 将 benchmark pipeline / task inventory / agent setup 的细节压回 Study Design，不和 deployment narrative 抢主线

**完成标准**
- 读者看完 Abstract + Intro 前两页，首先记住的是：**论文在回答部署决策**，不是又做了一轮 agent benchmark。

---

## 2. 现有 C/K/M 校准证据前置（不新增实验）

> 你补充的这一点要直接写进主文：**C/K/M 任务已经都人工审过，作为 calibration set。**

### 2.1 升级 calibration 的地位
- [ ] 在 Abstract/Intro/§2/§3 中明确写：**C/K/M = human-reviewed calibration set**
- [ ] 把当前 calibration 信息从“方法细节”升级成“结果可信度证据”
- [ ] 在 Results 里给一个单独小段或 boxed summary，集中呈现：
  - 12 calibration tasks
  - 96 runs
  - 3 blinded senior reviewers
  - 92.7% SE-PASS-vs-non-SE-PASS agreement
  - panel stricter than humans

### 2.2 调整威胁与未来工作措辞
- [ ] Threats 里不要让人读出“你们没有 human grounding”；要明确：**校准器已完成，只是 main corpus 尚未做人评扩展**
- [ ] Future Work 只保留“是否把 calibration 扩展到 CapBench main corpus”，不要让人误解为 C/K/M 本身还没做人评

**完成标准**
- reviewer 不会再说“你们只有 LLM judge，没有 human anchor”；而是会理解为：**human anchor 已存在，但目前覆盖的是 calibration set。**

---

## 3. 仅基于现有数据的重分析（不新增 run）

### 3.1 Judge validity：同族偏置分析
- [ ] 用现有每个 judge 的逐 run verdict / score，做 **leave-one-family-out** headline check：
  - Codex agent 的 headline verdict 不含 Codex judge
  - Claude agent 的 headline verdict 不含 Claude judge
  - Cursor / GLM 同理
- [ ] 计算 **same-family vs cross-family** score gap / verdict gap
- [ ] 在正文写成 robustness check，而不是另起新故事

**完成标准**
- 可以回答 reviewer：`headline 结论不依赖于同族 judge 给自己抬分。`

### 3.2 Gate 相关分析（仅做现有数据能支持的部分）
- [ ] 统一采用 Table 9 的真实数字：
  - semantic 44.7%
  - coverage 25.5%
  - design 10.9%
  - borderline 18.9%
- [ ] 将“哪些 gate 直接针对哪些 failure”写严谨：
  - Gate 3 直接针对 coverage
  - borderline 只能写成 *potentially recoverable / partially filterable*，不要写成已经被直接过滤
- [ ] 若现有 run-level / judge-level logs 足够，补一个 **post-hoc gate simulation（轻量版）**：
  - 用已有 failure signatures 估计各 gate 覆盖的失败质量
  - 不做任何新增 human pilot / online validation
- [ ] 若现有日志不足，则把 simulation 从主文降成 appendix 或删掉，避免空口断言

**完成标准**
- 从“gate 看起来合理”提升到“gate 与现有 failure distribution 的映射是可量化、可复核的”。

### 3.3 Prompt effect 的表述校正
- [ ] 保留“long prompts 提升 mean score”
- [ ] 强调“main corpus 上的 SE-PASS lift 全部来自 T10”
- [ ] 将 long prompt 定位成 **draft-quality lever**，不是 capability unlock

### 3.4 T10 处理统一化
- [ ] 所有 headline 数字同时给出：
  - inclusive：1.0%
  - T10-exclusive：0/392 = 0.0%
- [ ] 在 Abstract、Results、Conclusion、Threats 四处统一口径
- [ ] 将 T10 定义为 bounded / trivially scoped / single-file outlier，全文固定一种说法

### 3.5 若现有日志可提取，则补工业可行性指标（非新增实验）
- [ ] 从现有 timing metadata / session logs 中抽取 wall-clock latency
- [ ] 若已有 usage/token logs，则补 judge panel cost；若没有，不强写 token cost
- [ ] 从现有 artifacts 提取 compile / lint / test pass 统计（仅限已记录者）

**完成标准**
- 所有新增表/图都来自现有 logs / CSV / session metadata，不新增任何实验单元。

---

## 4. 任务选择透明度（只写清现有 curation，不新增任务）

### 4.1 把 selection process 写全
- [ ] 明确 CapBench 候选池大小（若已有 curation 记录）
- [ ] 明确过滤规则：feature not bugfix、≥2 source modules、upstream tests available
- [ ] 明确是否分层抽样，若不是分层抽样则直接说明
- [ ] 给出 project/language/complexity 覆盖摘要

### 4.2 讲清 Huawei backlog 与 task family 的映射
- [ ] 用文字解释：为什么 CANN / MindSpeed / Kubernetes 这三族可以代表目标部署对象
- [ ] 解释 main corpus 的 OSS family 与 Huawei deployment question 的对应关系
- [ ] 如果拿不出候选池分布，就**降低 claim**：
  - 不说“代表全部 backlog 分布”
  - 改说“用于 stress-test long-horizon feature delivery boundary”

**完成标准**
- reviewer 不会再轻易说“你们是刻意挑 hardest tasks”。

---

## 5. 图表与结果呈现重做（不新增实验）

### 5.1 Figure 6 / Table 9 一致性修复
- [ ] Figure 6 数字改成与 Table 9 完全一致：44.7 / 25.5 / 10.9 / 18.9
- [ ] 删除错误说法：`coverage + borderline ≈ 58%`
- [ ] 改成正确说法：`coverage + borderline = 44.4%`
- [ ] 若 borderline 不是“directly filterable”，图注里不要写过头

### 5.2 增加一张更有记忆点的 hero figure（仅用现有数据）
- [ ] 方案 A：**capability cliff figure**
  - x 轴按 task complexity / GT files 排序
  - y 轴画 task-level SE-PASS 或 mean score
  - 一眼看出 T10、Kubernetes cliff、49 non-trivial tasks = 0/392
- [ ] 方案 B：**gate-evidence figure**
  - failure signatures → gates
  - 每个 gate 对应的证据数字写清楚

### 5.3 图表风格统一
- [ ] Figure 1/2/5/6 避免都长成“流程图”
- [ ] 每张图只保留一个核心 message
- [ ] 图中数字、百分号、小数位统一格式

**完成标准**
- 至少有一张图能让 reviewer 在 rebuttal/poster 之后还记得住论文主结论。

---

## 6. 术语、编号、定义统一（全部属于直接修稿）

### 6.1 Gate 术语统一
- [ ] 全文统一成 **four-gate deployment pipeline / four-gate policy**
- [ ] 把 `five-step gating sequence` 改掉，避免与 Figure 5 冲突
- [ ] 若确实想保留 five-step，需要把“agent invocation”解释为 process step 而非 gate；否则一律删

### 6.2 Finding 编号重排
- [ ] 重新编号为 Finding 1–N
- [ ] 删除 `Finding 1b`, `Finding 4 (updated)`, 重复的 `Finding 5`, 以及无编号的 `Finding:`
- [ ] 结果段每个 finding 只承载一个 message

### 6.3 术语与命名统一
- [ ] `MindSpore-style refactors` 改成 `MindSpeed-style refactors`（如果是 typo）
- [ ] 若 MindSpore 和 MindSpeed 是两个不同系统，则必须显式解释关系
- [ ] `SE-PASS / se-pass / PASS` 大小写统一
- [ ] `main corpus / calibration subset / C/K/M / CapBench` 的命名统一

### 6.4 统计口径统一
- [ ] 统一使用 `SE-PASS-vs-non-SE-PASS agreement`，不要混用 `SE-PASS-vs-non-PASS`
- [ ] 统一 `majority verdict`, `3-of-4 majority`, `conservative tie-break` 的表述
- [ ] 统一“main corpus 400 runs / all 496 runs / T10-exclusive 392 runs”的使用语境

**完成标准**
- 全文不会再出现“概念漂移”“编号像 draft”“系统名不一致”这类低级失分点。

---

## 7. Placeholder / 引用 / 参考文献清零（必须一次做干净）

### 7.1 Front matter placeholders
- [ ] 替换 ACM header 中的 ISBN placeholder：`978-x-xxxx-xxxx-x/YYYY/MM`
- [ ] 替换 DOI placeholder：`10.1145/nnnnnnn.nnnnnnn`
- [ ] 替换 ACM Reference Format 里的 DOI placeholder

### 7.2 Data Availability placeholders
- [ ] 将 `Zenodo deposit (DOI fixed at camera-ready)` 改成最终 DOI
- [ ] 若当前还不能公开最终 DOI，则改成提交阶段可接受的明确写法，不要保留口语化占位句

### 7.3 In-text citation placeholders
- [ ] 补齐文中这些占位引用：
  - `ProdCodeBench [? ]`
  - `SWT-Bench [? ]`
  - `Meta’s test-gen pipeline [? ]`
  - `BitsAI-CR [? ]`

### 7.4 Reference list placeholders / 编号异常
- [ ] 把参考文献列表里所有 `[]` 空编号修正为正常编号
- [ ] 检查每个 in-text citation 都能在 bib 中找到唯一条目
- [ ] 检查 bib 中没有 orphan entry、重复 entry、未被引用 entry
- [ ] 统一 arXiv / conference / journal 的格式
- [ ] 统一 author 名字、大小写、标点、页码、DOI/URL 的格式

### 7.5 交叉检查
- [ ] reference numbering 从头到尾连续
- [ ] 文中引用顺序与文末编号一致
- [ ] 不再出现 `[?]`、`[]`、`TBD`、`camera-ready`、`nnnnnnn`、`978-x...` 这类占位符

**完成标准**
- 论文 PDF 中全局搜索不到任何 placeholder。

---

## 8. 语气降噪与可信度增强（纯写作修改）

### 8.1 收短 Abstract
- [ ] Abstract 只保留最关键的 3 组数字：
  - 1.0% / 0/392
  - 92.7% calibration agreement
  - 44.7% / 25.5% failure split
- [ ] 删去重复解释性句子，避免 Abstract 过满

### 8.2 收短 Introduction
- [ ] Intro 收成 **2 个 RQ + 3 个 contribution**
- [ ] 减少重复说“不是 benchmark 问题”
- [ ] 少做 product ranking，多做 deployment implication

### 8.3 降低过度外推
- [ ] `now in production` 如果没有线上 funnel 证据，改成更稳妥表述：
  - `used in the current internal rollout policy`
  - `adopted in internal routing decisions`
- [ ] `Every gate is justified` 改成 `Each gate is motivated by evidence from the audit`
- [ ] `Current agents are not ready...` 后加限定范围：`under our protocol / on these task families`

### 8.4 强化“保守下界”表述
- [ ] 保留 strict-equivalence 的保守性解释
- [ ] 但不要把 acceptability 的讨论埋在 Threats 最深处
- [ ] 用现有 calibration 结果支持“panel is conservative lower bound”这一句

**完成标准**
- 语言更克制，结论更像顶会 industry paper，而不是立场宣言。

---

## 9. 终稿 QA（逐项对数）

### 9.1 数字一致性检查
- [ ] 1.0% / 0/392 / 1.6%
- [ ] 7.5% / 4.2% / 0/32
- [ ] 92.7% agreement
- [ ] 44.7 / 25.5 / 10.9 / 18.9
- [ ] 44.4% combined（不是 58%）

### 9.2 章节与交叉引用检查
- [ ] Figure / Table / Section / Finding 编号全部连续
- [ ] 文中对 Figure 5 / Figure 6 / Table 9 的引用准确
- [ ] 所有 appendix / artifact bundle 的引用存在且命名一致

### 9.3 术语与 claim 检查
- [ ] four-gate 口径全篇一致
- [ ] MindSpeed/MindSpore 不再混淆
- [ ] calibration / main corpus / CapBench / C/K/M 的层级清楚
- [ ] `human calibration exists` 与 `main corpus human re-rating future work` 不冲突

**完成标准**
- reviewer 在第一遍通读时不会被数字、图、术语、引用问题打断信任。

---

## 10. 可直接贴到任务系统的执行顺序

### P0（先做）
- [ ] Figure/Table/数字/术语/编号/placeholder 全部清零
- [ ] 把 C/K/M 人工校准器前置到主文
- [ ] 改写 Abstract / Intro / §5 / Conclusion 的 deployment framing

### P1（第二轮）
- [ ] judge bias 现有数据重分析
- [ ] task selection transparency 补写
- [ ] T10 / prompt effect / failure decomposition 口径统一

### P2（第三轮）
- [ ] hero figure 重做
- [ ] latency / CI / cost（仅限现有 logs 可提取项）
- [ ] 全文压缩 15–20%

---

## 11. 这版 **明确不做** 的事（避免 scope creep）

- [ ] 不新增 online pilot
- [ ] 不新增 main corpus RA-PASS 人评
- [ ] 不新增 CapBench stratified human calibration
- [ ] 不新增 agent rerun / k=5 reproducibility 实验
- [ ] 不新增新的 benchmark task 或新的 agent 配置

