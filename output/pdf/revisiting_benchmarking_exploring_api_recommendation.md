# Revisiting, Benchmarking and Exploring API Recommendation: How Far Are We?

> 原文 PDF: `ref_sources/Revisiting, Benchmarking and Exploring API Recommendation How Far Are We.pdf`  
> 整理方式: 按原论文章节顺序整理，保留核心数据、RQ、Findings 与 Implications。

## 论文信息

- 标题: Revisiting, Benchmarking and Exploring API Recommendation: How Far Are We?
- 作者: Yun Peng, Shuqing Li, Wenwei Gu, Yichen Li, Wenxuan Wang, Cuiyun Gao, Michael Lyu
- 机构: The Chinese University of Hong Kong; Harbin Institute of Technology, Shenzhen; Guangdong Provincial Key Laboratory of Novel Security Intelligence Technologies; Peng Cheng Laboratory
- 主题: API recommendation, benchmark, empirical study
- 核心产物: APIBench, 一个同时覆盖 query-based 与 code-based API recommendation 的基准。

## Abstract

论文关注 API 推荐任务的定义不统一与评测不可复现问题。已有研究有的把 API 推荐视为代码补全问题，有的根据自然语言查询推荐相关 API，导致不同方法之间难以公平比较。作者将 API 推荐划分为两类:

- Query-based API recommendation: 输入自然语言需求查询，推荐相关 API。
- Code-based API recommendation: 基于推荐点周围已有代码上下文，预测下一个 API。

论文研究了 11 个近期方法与 4 个常用 IDE，并构建 APIBench 分别评测两类任务。基于实验，论文总结了 API 推荐的关键挑战与改进方向，包括查询改写、数据源选择、低资源场景、用户自定义 API、以及带使用模式的 API 推荐。

## 1 Introduction

API 是现代软件开发的基础，但 API 数量巨大，开发者很难熟悉所有 API。例如 Java 标准库提供超过 30,000 个 API。已有 API 推荐方法主要依赖两类输入:

- 自然语言查询: 描述开发者的编程需求。
- 代码上下文: 开发者已经写好的代码。

论文指出当前领域的主要问题是任务定义和评测方式不统一。有些工作预测任意代码 token，其中 API 只是 token 的一类；有些工作直接根据自然语言查询推荐 API。Query-based 任务常依赖人工评价，code-based 任务又常与 IDE 或搜索引擎比较，评测口径难以对齐。

作者据此提出两类任务定义:

- Query-based API recommendation: 根据自然语言需求查询，帮助开发者知道应该使用哪个 API。
- Code-based API recommendation: 根据推荐点附近代码，预测下一步可能调用的 API，直接服务代码编写效率。

### 研究问题

论文围绕 APIBench 研究 6 个问题:

| RQ | 问题 |
| --- | --- |
| RQ1 | 当前 query-based 与 code-based API 推荐方法有多有效? |
| RQ2 | 查询改写技术对 query-based API 推荐有何影响? |
| RQ3 | 不同数据源对 query-based API 推荐有何影响? |
| RQ4 | Code-based 方法对不同类型 API 的推荐能力如何? |
| RQ5 | Code-based 方法处理不同上下文时表现如何? |
| RQ6 | Code-based 方法在跨领域项目中的表现如何? |

### 关键发现概览

Query-based API recommendation:

- 当前方法在 class-level 推荐上已有进展，但精确推荐 method-level API 仍然困难。
- 查询改写，包括 query expansion 和 query modification，对性能提升明显。
- Stack Overflow、教程等更贴近真实查询的数据源能显著改善推荐效果。

Code-based API recommendation:

- Transformer 等深度学习模型表现优于传统方法；常用 IDE 的 API 推荐能力也很强，并非简单按字母序推荐。
- 当前方法对标准库和流行第三方库较有效，但对 user-defined / project-specific API 性能下降明显。
- 单一领域训练存在跨领域适应问题；多领域训练通常比单领域训练更稳健。

### 贡献

- 系统研究 query-based 与 code-based 两类 API 推荐任务。
- 构建并开放 APIBench，覆盖 Java 和 Python 的大规模数据。
- 研究查询质量、数据源、API 类型、上下文长度、推荐位置、跨领域等因素对推荐性能的影响。
- 提炼后续研究方向: 查询改写、更多数据源、few-shot learning、用户自定义 API 推荐等。

## 2 Background and Related Work

## 2.1 Query-Based API Recommendation Methods

Query-based API 推荐的典型流程包括三步:

1. 开发者输入自然语言查询。
2. 系统可先对查询做改写，包括扩展、替换或删除词。
3. 系统基于知识库检索或学习 query 与 API 的关系，返回候选 API。

### 2.1.1 Query Reformulation Techniques

论文将查询改写分为两类:

- Query expansion: 向原始查询中添加额外信息，例如相关词、API class 名称、module 名称。
- Query modification: 修改、替换或删除原查询中的词，缓解用户查询与 API 文档之间的词汇差异和知识差异。

在 API 推荐中，class 名称和 module 名称往往是重要线索。例如 NLP2API 会预测与查询相关的 API class，并把该 class 加入查询，缩小后续推荐范围。

### 2.1.2 Recommendation with Knowledge Base

API 推荐一般需要知识库作为搜索空间。论文提到三类常见知识源:

- 官方文档: 提供 API 功能和结构的系统描述。
- Q&A 论坛: 如 Stack Overflow，包含开发者的实际问题和 API 使用方式。
- Wiki 站点: 提供概念层面的 API 关联信息。

方法上又分为两类:

- Retrieval-based methods: 根据 query 与 API 或知识图谱片段的相似度排序候选 API。
- Learning-based methods: 使用 query-API 对训练模型，学习自然语言查询到 API 序列的映射，例如 RNN encoder-decoder。

## 2.2 Code-Based API Recommendation Methods

Code-based API 推荐基于推荐点之前或周围的代码上下文，预测下一步调用的 API。核心是如何表示上下文。

### 2.2.1 Context for the Target Code

论文区分两类上下文:

- Internal context: 当前源文件或当前函数体内、推荐点之前的代码。
- External context: 当前文件之外的实现，例如外部 API 的实现代码。已有工作发现引入外部实现有助于识别常见 API 使用模式。

### 2.2.2 Context Representation

上下文表示主要分为:

- Pattern-based representation: 只抽取 API usage sequence、API matrix、API dependency graph 等结构。
- Learning-based representation: 使用 token flow、AST、data flow 等更细粒度代码特征。

### 2.2.3 Recommendation Based on Context

Pattern-based 方法通常把 API 推荐看作推荐系统问题，例如把当前上下文视为 user，把 API 视为 item，通过相似度或关联规则推荐 API。

Learning-based 方法把 API 作为代码 token，转化为 next-token prediction。较新的方法还会结合 AST、data flow 等结构信息，以提升预测准确性。

## 3 Methodology

## 3.1 Scope of APIs

论文聚焦 Java 和 Python，并将 API 分为三类:

- Standard APIs: 语言或平台内建并有明确官方文档的 API。
- Popular third-party APIs: 流行第三方库 API。
- User-defined APIs: 项目内部定义并调用的函数或方法。

Query-based 评测只使用标准 API，因为标准 API 有较完整文档和讨论数据。Code-based 评测覆盖三类 API。

具体收集范围:

| 类型 | 数量与说明 |
| --- | --- |
| Java 标准 API | Java 8 官方文档中 34,072 个 API |
| Android API | Android 官方文档中 11,802 个 API |
| Python 标准 API | Python 3.9 标准库中 5,241 个 API |
| Python 第三方 API | Flask 215, Django 700, Matplotlib 4,089, Pandas 3,296, NumPy 3,683 |
| User-defined API | 项目内可定位实现的函数或方法 |

## 3.2 Benchmark Datasets

APIBench 包含两个数据集:

- APIBench-Q: 面向 query-based API 推荐。
- APIBench-C: 面向 code-based API 推荐。

### 3.2.1 Creation of APIBench-Q

APIBench-Q 来自 Stack Overflow 和 API tutorial websites。

Stack Overflow 部分:

- 数据时间范围: 2008 年 8 月到 2021 年 2 月。
- 原始帖子量: Java 1,756,183 条，Python 1,661,383 条。
- 初步过滤规则: 需要有回答或认可答案、包含 `<code>`、代码片段不超过两行、代码中包含论文研究范围内的 API。
- 过滤后: Python 156,493 条、Java 148,938 条 API 相关帖子。
- 人工标注: 16 名参与者，每条至少两人判断；Fleiss Kappa 为 0.77。
- 最终保留: 3,245 条 Stack Overflow 查询，其中 Python 1,925 条、Java 1,320 条。

Tutorial websites 部分:

- 来源: GeeksforGeeks、Java2s、Kode Java。
- 最终收集: Java 5,243 条，Python 2,384 条。

APIBench-Q 总规模:

| 来源 | Python | Java |
| --- | ---: | ---: |
| Stack Overflow | 1,925 | 1,320 |
| Tutorial websites | 2,384 | 5,243 |
| 合计 | 4,309 | 6,563 |

论文没有为 APIBench-Q 统一划分训练集，因为不同 query-based 方法本身依赖的数据源差异很大。为避免数据泄漏，作者在预处理时去除与各方法训练数据重叠的样本。

### 3.2.2 Creation of APIBench-C

APIBench-C 来自 GitHub，用于 code-based API 推荐。作者按语言分别选择多个领域:

- Python: General, Machine Learning, Security, Web, Deep Learning。
- Java: General, Android, Machine Learning, Testing, Security。

项目选择方式:

- 特定领域: 按 GitHub topic 选取 star 最多和 fork 最多的项目。
- General 领域: 不区分 topic，按 star 和 fork 选热门项目。
- 过滤规则: 少于 10 个文件、少于 1000 行代码、目标语言代码比例低于 10% 的仓库被移除。
- 训练测试划分: 按项目级别 80% / 20% 划分，避免同一项目同时出现在训练集和测试集造成泄漏。

总体规模:

- Python: 2,223 个项目，414,753 个源文件。
- Java: 1,477 个项目，1,229,698 个源文件。

论文还基于函数长度研究上下文影响。大多数 Python 函数为 5-30 LOC，大多数 Java 函数为 5-20 LOC。作者按 90% 置信区间将函数分为 extremely short、moderate、extremely long 三类。

## 3.3 Implementation Details

### Query reformulation techniques

论文评测四类查询改写工具:

- Google Prediction Service
- NLPAUG
- SEQUER
- NLP2API

### Query-based API recommendation approaches

评测方法包括:

- RACK
- KG-APISumm
- Naive Baseline
- DeepAPI
- Lucene
- BIKER

不同方法使用的数据源不同。例如 Naive Baseline 和 DeepAPI 只使用官方文档；BIKER 和 RACK 还使用 Stack Overflow；KG-APISumm 使用官方文档和 Wikipedia。

### Code-based API recommendation approaches

评测对象包括 4 个 IDE 和 5 个学术方法:

| 类别 | 方法 |
| --- | --- |
| IDE | PyCharm, Visual Studio Code, Eclipse, IntelliJ IDEA |
| 学术方法 | TravTrans, PyART, Deep3, FOCUS, PAM |
| 扩展基线 | PAM-MAX |

PAM-MAX 是作者扩展的理论上限版本，用于估计 context-insensitive 方法在跨项目设置中的最好表现。

### Evaluation metrics

论文使用排序推荐常见指标:

- Success Rate@k: Top-k 结果中是否包含正确 API，不考虑顺序。
- MAP
- MRR
- NDCG

NDCG 中，命中正确 API class 的 relevance score 为 1，命中正确 API method 的 relevance score 为 2，用于统一衡量 class-level 和 method-level 表现。

## 4 Empirical Results of Query Reformulation and Query-Based API Recommendation

本节回答 RQ1-RQ3。由于当时没有专门面向 Python API 的 query-based 方法，实验主要关注 Java。

## 4.1 Effectiveness of Query-Based API Recommendation Approaches (RQ1-1)

论文在 APIBench-Q 的原始查询上评测六个 query-based 方法。

### Class-level vs. Method-level

BIKER 在 class-level 上表现最好，Success Rate@10 达到 0.67。但 method-level 明显更难，BIKER 的 Success Rate@10 下降到 0.37，DeepAPI 和 Lucene 的 method-level Success Rate@10 只有约 0.10。

核心结论:

- 当前方法能较好定位 API class，但精确推荐 API method 仍然困难。
- 平均来看，在已经能命中 class 的情况下，仍有 57.8% 的 method-level API 无法准确推荐。

### Retrieval-based vs. Learning-based

实验中 retrieval-based 方法整体优于 learning-based 方法:

| 方法类型 | Class-level Top-10 命中 | Method-level Top-10 命中 |
| --- | ---: | ---: |
| Retrieval-based | 46.8% | 25.5% |
| Learning-based | 25.5% | 8.0% |

作者认为原因之一是 query-API 训练数据不足。标准 API 超过 30,000 个，而 Stack Overflow 经预处理后只有约 150,000 条可用帖子，对学习式方法仍然偏少。

### Ranking performance

Success Rate 与 MAP/NDCG 之间差距明显。例如 RACK 的 Success Rate@10 为 0.41，但 MAP@10 只有 0.24。这说明即使模型能找到正确 API，也常不能把它排在靠前位置。

本节 Findings:

- Finding 1: Method-level API 推荐仍远未达到实用要求。
- Finding 2: Learning-based 方法不一定优于 retrieval-based 方法，训练数据不足是重要限制。
- Finding 3: 当前方法的 API ranking 能力仍不足。

## 4.2 Effectiveness of Query Reformulation Techniques (RQ2)

论文将查询改写应用到所有 query-based 方法上，并从两个角度分析:

- 是否能帮助模型命中更多正确 API。
- 是否能改善正确 API 的排序位置。

每个原始 query 会被改写 10 次，作者选择最佳改写结果分析其潜在上限。

### 4.2.1 Influence on Predicting More Correct APIs

整体上，查询改写有效提升推荐准确率:

- Class-level 平均提升 0.11，对应 27.7% boost。
- Method-level 平均提升 0.08，对应 49.2% boost。

Query expansion 比 query modification 更稳定:

| 改写类型 | Class-level 平均提升 | Method-level 平均提升 |
| --- | ---: | ---: |
| Query expansion | 0.13 | 0.10 |
| Query modification | 0.09 | 0.06 |

具体方法上:

- NLP2API 和 NLPAUG(BERT) 改写效果最好。
- 添加预测出的 API class 或相关语义词，比添加普通 token 更有用。
- Word2Vec 类方法可能加入无关词，反而损害推荐。
- BERT-based data augmentation 在 query modification 中优于其他修改方法。

本小节 Findings:

- Finding 4: 查询改写显著提升 query-based API 推荐命中率。
- Finding 5: Query expansion 比 query modification 更稳定、更有效。
- Finding 6: 添加预测 API class 名称或相关词，比添加其他 token 更有用。
- Finding 7: BERT-based data augmentation 在 query modification 中表现最好。

### 4.2.2 Influence on API Ranking

论文使用 NDCG@1 分析排序影响，只统计改写前后都能命中的样本，以排除命中率变化的干扰。

结果:

- 大多数 query expansion 技术能改善排序。
- NLP2API 在 Lucene 上带来最大 NDCG@1 提升: 0.14，即 32% boost。
- Query expansion 平均提升 MRR: class-level +0.09，method-level +0.08。
- Query modification 效果较弱，平均 NDCG@1 只提升 0.01；WordNet 和 random modification 还可能造成下降。

Finding 8: 合适的 query expansion 或 query modification 不仅能增加命中率，还能提升正确 API 的排名。

### 4.2.3 Word Deletion

论文额外分析了随机删词这种特殊 query modification，用来判断用户查询中是否存在噪声词。

结果有两面:

- 平均表现下降: class-level 下降 13%，method-level 下降 18%，说明大多数词仍有帮助。
- 但最佳删词版本提升明显: class-level 平均提升 38%，method-level 平均提升 64%，说明某些查询确实存在噪声词。

作者人工分析了 545 个删词后变好的查询，噪声词主要有三类:

| 噪声类型 | 数量 | 占比 |
| --- | ---: | ---: |
| 不必要或无意义词 | 349 | 64% |
| 解释过细的词 | 156 | 29% |
| 过长描述 | 34 | 6% |

Finding 9: 用户原始查询常包含会误导推荐的噪声词，未来查询改写应考虑 noisy-word deletion。

## 4.3 Data Sources (RQ3)

论文比较官方文档、Stack Overflow、二者混合三种知识库设置对推荐结果的影响。实验使用 Lucene 和 Naive Baseline，因为它们方便切换数据源。

结果显示，Stack Overflow 相比官方文档明显更有效:

- Lucene 使用 Stack Overflow 后，class-level 提升 29%，method-level 提升 169%。
- Naive Baseline 使用 Stack Overflow 后，class-level 提升 71%，method-level 提升 602%。

原因:

- Stack Overflow 的表达更接近开发者真实查询。
- 官方文档描述通常更规范，但未必覆盖 API 的实际扩展用法。
- Q&A 中常包含开发者如何把抽象 API 用在具体任务中的讨论。

Finding 10: 除官方文档外，引入 Stack Overflow 等数据源能显著提升 query-based API 推荐性能。

## 5 Empirical Results of Code-Based API Recommendation

本节回答 RQ1 的 code-based 部分以及 RQ4-RQ6。RQ1、RQ4、RQ5 在 General domain 上评估；RQ6 在多个领域间做跨领域评估。

## 5.1 Effectiveness of Existing Approaches (RQ1-2)

论文首先在 APIBench-C General domain 上评测 code-based 方法。

Python 结果:

- TravTrans 最好，Success Rate@10 为 0.62，NDCG@10 为 0.54。
- PyART 的 Success Rate@10 为 0.60，但由于训练测试成本高，只在 20% 抽样上评测。
- Deep3 的 Success Rate@10 为 0.43。

Java 结果:

- FOCUS 和 PAM 表现较弱，Success Rate@10 分别为 0.06 和 0.05。
- PAM-MAX 达到 0.45，代表 context-insensitive 类方法的理论上限仍不及细粒度学习方法。

作者认为 code-based 任务中学习式方法表现更好，是因为公开代码仓库提供了大量结构化训练数据。

### IDE 对比

论文还人工抽样 500 个 API case，比较常用 IDE:

| 语言 | 工具或方法 | Success Rate@10 | NDCG@10 |
| --- | --- | ---: | ---: |
| Python | TravTrans | 0.50 | 0.44 |
| Python | PyCharm | 0.49 | 0.40 |
| Python | VSCode | 0.35 | 0.18 |
| Java | PAM-MAX | 0.56 | 0.39 |
| Java | Eclipse | 0.60 | 0.42 |
| Java | IntelliJ IDEA | 0.67 | 0.55 |

Finding 11: TravTrans 等深度学习模型在 code-based API 推荐上表现突出；常用 IDE 也能达到相当强的推荐性能。

## 5.2 Capability to Recommend Different Kinds of APIs (RQ4)

论文比较当前方法推荐三类 API 的能力:

- Standard APIs
- Popular third-party APIs
- User-defined APIs

结果:

- 标准库 API 推荐效果最好。TravTrans 对 standard APIs 的 Success Rate@10 超过 90%。
- 流行第三方库 API 也较好，TravTrans 的 Success Rate@10 超过 0.8。
- 用户自定义 API 是主要瓶颈。相比 standard APIs，方法在 user-defined APIs 上失败率多出 35.3% 到 91.3%。

原因:

- 标准库和流行第三方库在训练数据中出现频繁。
- User-defined APIs 往往只在当前项目内出现，机器学习模型难以在训练集中学到，pattern-based 方法也难以挖掘到稳定模式。

Finding 12: 当前方法虽然能较好推荐标准库和流行第三方库 API，但仍难以准确推荐 user-defined APIs。

## 5.3 Capability to Handle Different Contexts (RQ5)

论文研究两类上下文因素:

- 函数长度，即上下文长短。
- 推荐点位置，即推荐点在函数前部、中部、后部。

### Function length

大多数方法在 moderate-length 函数上表现最好，在 extremely short 和 extremely long 函数上下降:

- 极长函数平均下降 7.1%。
- 极短函数平均下降 10.6%。

作者认为极短函数上下文信息不足，而极长函数可能引入过多干扰信息。极短函数更具挑战。

Finding 13: 上下文长度会影响推荐效果，极短和极长函数都会降低性能，其中极短函数更难。

### Recommendation point location

论文将推荐点分为:

- Front: 行位置和 API 序号都位于函数前 1/4。
- Middle: 位于函数中间 1/2。
- Back: 位于函数后 1/4。

结果:

- Front 推荐点最难，平均 Success Rate@10 为 0.316，因为可用上下文最少。
- Back 推荐点虽然上下文最多，但并非所有方法都表现最好；过多上下文可能造成信息过载。

Finding 14: 推荐点位置会影响当前方法性能；front 位置因上下文不足最难，部分方法在 back 位置会受过量上下文影响。

## 5.4 Adaptation to Cross-Domain Projects (RQ6)

论文在 Python 的四个具体领域上研究跨领域表现，评测 TravTrans、Deep3、PyART。

主要结果:

- 单领域训练通常在同领域测试上最好。
- 跨领域推荐会下降，性能下降范围为 2.1% 到 43.1%。
- 在 General domain 上训练，即多领域数据训练，通常在各单领域上表现最好。

TravTrans 在 General domain 训练后的 Success Rate@10:

| 测试领域 | Success Rate@10 |
| --- | ---: |
| ML | 0.72 |
| Security | 0.76 |
| Web | 0.78 |
| DL | 0.74 |

多领域训练相比单领域训练平均提升约 14%。

Findings:

- Finding 15: 使用细粒度上下文表示的方法对训练数据领域敏感，跨领域推荐会下降。
- Finding 16: 多领域训练能帮助当前方法在单领域项目中推荐 API，通常优于只在单领域训练。

## 6 Discussion and Future Work

## 6.1 Query Reformulation for Query-Based API Recommendation

查询改写应成为 query-based API 推荐的常规预处理步骤。论文指出，基于改写后的查询，BIKER 在 class-level API 推荐上的 Success Rate@10 可达到 0.80，在 method-level 上可达到 0.51。

未来方向:

- 更系统地选择 query expansion 或 query modification 策略。
- 检测并删除查询中的噪声词。
- 将预测 API class、BERT 相关词增强等策略整合到推荐流程中。

Implication 1: 当前 query-based API 推荐方法应与查询改写技术结合。

## 6.2 Data Sources for Query-Based API Recommendation

只依赖官方文档会受到两个限制:

- Query-API pairs 不足，限制 learning-based 方法。
- 用户查询与官方 API 描述存在语义差距。

Stack Overflow 等数据源能更好反映开发者真实表达和实际用法，因此是弥合 query 与 API 之间差距的重要补充。

Implication 2: 除查询改写外，加入合适的数据源也是连接用户查询与 API 的有效方式。

## 6.3 Low Resource Setting in Query-Based API Recommendation

Query-based API 推荐是典型低资源场景。可用的高质量 query-API pairs 有限，导致 learning-based 方法未必优于 retrieval-based 方法。

论文观察到 BERT 等预训练模型在 query reformulation 中表现强，说明预训练模型可能隐式缓解用户查询与 API 描述之间的语义差距。

Implication 3: Few-shot learning 与强预训练模型可能是提升 query-based API 推荐的重要方向。

## 6.4 User-Defined APIs

User-defined API 是 code-based API 推荐的主要瓶颈。原因是这些 API 通常不会出现在训练集中，机器学习模型难以学习，pattern-based 方法也难以挖掘。

仅把 user-defined API 当作普通 code token 预测也不够，因为如果该 token 从未在前文出现，模型仍难以正确预测。

Implication 4: User-defined API 推荐仍未解决，是提升 code-based API 推荐实用性的关键问题。

## 6.5 Query-Based API Recommendation with Usage Patterns

论文指出，仅推荐 API 名称还不够，开发者还需要知道如何正确使用 API。官方文档能提供签名和约束，但未必包含足够使用场景。

可能方向:

- Query-based 方法负责推荐目标 API。
- Code-based pattern mining 负责从代码库中提取常见使用模式。
- 推荐结果同时返回 API 和 usage pattern，降低 API misuse 风险。

Implication 5: Code-based API 推荐方法可以为 query-based API 推荐补充使用模式。

## 6.6 Implications for Different Group of Software Practitioners

对研究者:

- Query-based API 推荐应进一步系统研究查询改写的作用因素。
- Code-based API 推荐应重点解决 user-defined API 推荐问题。

对 API 设计者和文档作者:

- 官方文档应提供更多真实示例和更自然语言化的描述，降低用户查询与 API 文档之间的知识差距。

对 API 搜索用户:

- 查询应尽量使用专业、简洁的表达。
- 避免过长描述和无关信息，因为噪声词会误导推荐系统。

## 7 Threat to Validity

## 7.1 Internal Validity

论文讨论三类内部威胁:

- Baseline re-implementation: 部分基线不是专门为 API 推荐设计，作者需要修改其代码以适配 APIBench，因此结果可能与原论文略有差异。作者通过参考相关复现与引用工作来校验结果合理性。
- Data quality: APIBench-Q 依赖人工筛选和标注，可能受主观因素影响。作者使用至少两人标注、一名作者仲裁，并计算一致性指标。
- Identification of user-defined APIs: 用户自定义 API 通过静态 import analysis 识别，但静态分析完整性仍是开放问题，可能漏掉部分 user-defined API。

## 7.2 External Validity

论文讨论两类外部威胁:

- Data selection: APIBench 已尽量从 GitHub 热门领域和 Stack Overflow 真实查询中构建，但在其他数据集和领域上可能存在差异。
- Programming language: 研究只覆盖 Python 和 Java，结论未必完全泛化到其他语言。不过作者认为 Python 和 Java 分别代表动态类型和静态类型语言，因此仍有较强代表性。

## 8 Conclusion and Future Work

论文完成了对 API 推荐任务的系统回顾、分类和基准评测，并提出 APIBench 统一评估 query-based 与 code-based 方法。

Query-based 结论:

- Method-level API 推荐仍然困难。
- 查询改写能显著提升查询质量和推荐性能。
- 用户查询中存在噪声词，简单删词在部分样本上就能提升效果。
- Stack Overflow 等数据源能缓解用户查询与官方文档描述之间的语义差距。

Code-based 结论:

- Transformer 等深度学习方法表现优越。
- 用户自定义 API 是当前主要瓶颈。
- 上下文长度和推荐点位置会显著影响性能。
- 跨领域训练存在性能下降，多领域训练更稳健。

未来工作:

- 对推荐 API 的摘要和使用说明进行主观质量评估。
- 更全面研究 query reformulation 技术如何服务 API 推荐。
- 用 few-shot learning 和更丰富数据源缓解 query-based 低资源问题。
- 提升 user-defined API 推荐能力。

## 附: 论文中的核心 Findings 与 Implications

### Findings

1. 当前方法仍难以精确预测 method-level API。
2. Learning-based query 推荐方法受限于 query-API 数据不足，不一定优于 retrieval-based 方法。
3. 当前 query-based 方法的 API ranking 仍不够好。
4. 查询改写能显著提升 query-based API 推荐命中率。
5. Query expansion 通常比 query modification 更稳定有效。
6. 添加 API class 或相关词，比添加普通 token 更有帮助。
7. BERT-based data augmentation 在 query modification 中表现突出。
8. 合适的查询改写也能提升 API 排名。
9. 用户原始查询常包含噪声词，noisy-word deletion 值得研究。
10. Stack Overflow 等额外数据源能显著提升 query-based API 推荐。
11. TravTrans 等深度学习模型和常用 IDE 在 code-based API 推荐中表现较强。
12. User-defined API 推荐是当前方法的重要短板。
13. 上下文长度影响推荐性能，极短和极长上下文都会带来困难。
14. 推荐点位置影响性能，front recommendation point 最难。
15. 细粒度上下文方法对训练领域敏感，跨领域推荐会下降。
16. 多领域训练通常比单领域训练更有利于跨领域推荐。

### Implications

1. Query-based API 推荐应结合查询改写。
2. 应引入更贴近真实查询的数据源。
3. Few-shot learning 与强预训练模型适合低资源 query-based API 推荐。
4. User-defined API 推荐是 code-based API 推荐的关键未解问题。
5. Code-based usage pattern 可增强 query-based API 推荐结果。
