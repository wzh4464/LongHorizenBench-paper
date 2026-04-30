# Comments extracted from main_peng.pdf

- Source: `main_peng.pdf`
- Total comments: 52
- Order: PDF page order, then annotation order on each page

## Page 1

1. 不要在正文中直接提huawei，写某大型ICT公司就行。我看你全篇都在提，你去看看之前的ind的paper，看看有没有提公司，有的话也行吧。。。  
   - YUN PENG | 2026-04-29 11:58:00 +08:00

2. 这个写的太奇怪了，你要写现在coding agents刷榜刷的很厉害，但是在实际开发过程中的效果未知。  
   - YUN PENG | 2026-04-29 15:32:32 +08:00

3. contribution是放到最后讲的，如果这是你的方法，那要motivate一下为啥需要这个方法，每一个gate的作用是啥。  
   - YUN PENG | 2026-04-29 15:34:57 +08:00

4. 没有看出来这部分跟前面那一段之间的关系，如果是个empirical study的话，这部分应该才是主要的内容，那前面那一段就要motivate你这个empirical study，为啥要选这些instance  
   - YUN PENG | 2026-04-29 15:36:02 +08:00

5. 这种公司政策方面的claim要慎重，容易被合规审计。  
   - YUN PENG | 2026-04-29 15:41:31 +08:00

6. 这个问题跟现在的FEABench、SWEBench之类的有何区别？需要在问题里面就要明确，比如说agent在工业级/系统级的开发能力如何？  
   - YUN PENG | 2026-04-29 15:42:16 +08:00

7. 这里我建议是往工业级/系统级去说，然后顺带说一下是文件和代码修改很多的  
   - YUN PENG | 2026-04-29 15:43:36 +08:00

8. 你这个empirical study应该不算audit吧，只是一个evaluation，audit用词感觉太严重了  
   - YUN PENG | 2026-04-29 15:44:14 +08:00

9. 如何定义long horizon，这里第一次出现，其实应该在前面就要关联一下这个次，还要跟SWEBench Pro做出区别，人家title里面就有这个词。  
   - YUN PENG | 2026-04-29 15:44:45 +08:00

## Page 2

10. 这里为啥要用both开源和华为的项目，需要说明一下，怕开源的存在严重的数据泄露啥的。  
   - YUN PENG | 2026-04-29 15:45:44 +08:00

11. 这个不需要在intro里面讲，在你后面的design和结果里面去讲就行了。  
   - YUN PENG | 2026-04-29 15:47:55 +08:00

12. 先写empirical study的findings，再写整篇paper的contributions，你这个C1的contribution如果没有eval的话建议不要提，要不然肯定会被喷  
   - YUN PENG | 2026-04-29 15:48:27 +08:00

13. 这两个findings是想说明啥，第一个finding已经说明agent做不出来了，第二个finding是啥意思？  
   - YUN PENG | 2026-04-29 15:50:56 +08:00

14. 这个finding可能会被喷，有可能是long prompt包含的信息还是不足，或者说是agent没有办法理解非常长的文档？  
   - YUN PENG | 2026-04-29 15:51:52 +08:00

15. 这个你直接说agents失败的原因有那几类就行了，不用说你的gate啥的方法  
   - YUN PENG | 2026-04-29 15:53:05 +08:00

16. empirical study要先设置research question，你要在intro里面就列出来哪几个问题你要研究，然后针对这些RQ去设置实验  
   - YUN PENG | 2026-04-29 16:10:59 +08:00

## Page 3

17. 你要说一下为啥找这几个project，比如他们有名，开发符合规范，有各种长文档的需求和对应的PR啥的。  
   - YUN PENG | 2026-04-29 15:54:37 +08:00

18. 这个你应该在intro就要提，而且要说明跟之前benchmark的差别，最好是提一下系统级/模块级区别之前benchmark的文件级，这样看起来比较软工  
   - YUN PENG | 2026-04-29 15:55:14 +08:00

19. 这里应该只说数据是咋来的吧，这个90多的agreement是咋来的？  
   - YUN PENG | 2026-04-29 15:57:32 +08:00

20. 你这里怎么又讲怎么选的了，要到前面一起讲  
   - YUN PENG | 2026-04-29 15:58:46 +08:00

## Page 4

21. 这个表格有点太稀疏了，应该可以缩小很多，我给你的那50个instance最好也简单列一下分布，两个benchmark直列一个数据太奇怪了，reviewer一般都不会看replication package  
   - YUN PENG | 2026-04-29 16:00:16 +08:00

22. 你这个N是啥？没有解释  
   - YUN PENG | 2026-04-29 16:02:46 +08:00

23. 所有缩写都要解释，要不然就写全  
   - YUN PENG | 2026-04-29 16:03:51 +08:00

24. 这个写的太简单了，我是建议列一个EP的大概格式出来，然后图示说你选了哪部分做short prompt，哪部分做long prompt  
   - YUN PENG | 2026-04-29 16:04:15 +08:00

25. 我看似乎全是LLM as a judge，软工对这个比较敏感，你去看下SWE-QA之类的paper是咋评的，写的看起来solid一点  
   - YUN PENG | 2026-04-29 16:05:41 +08:00

26. 你可能也要提一下大规模的修改跑testcase耗时耗力，testcase粒度太粗，错1行和错2000行都是错，也与工业界的要求不符，因为公司还是看入库率，错了一点手动改一下能入库也可以  
   - YUN PENG | 2026-04-29 16:07:13 +08:00

27. 你目前的章节数量太少了，可以把evaluation拆成一章来写。  
   - YUN PENG | 2026-04-29 16:10:11 +08:00

## Page 5

28. 你要说一下你用了什么CPU型号，用啥调的模型，机器多大内存啥的  
   - YUN PENG | 2026-04-29 16:09:21 +08:00

29. Empirical Results  
   - YUN PENG | 2026-04-29 16:10:37 +08:00

30. 这个section要用RQ来organize，不能想到啥写啥，这样没有系统性  
   - YUN PENG | 2026-04-29 16:11:53 +08:00

31. finding最好用一个框框起来，然后背景用颜色高亮，比较显眼。  
   - YUN PENG | 2026-04-29 16:12:17 +08:00

32. 你的数据表呢，就算效果很差也要放表。。。Table 4是两个benchmark集合的结果，最好还是在Table 4里面区分一下，这样你在这里也可以reference  
   - YUN PENG | 2026-04-29 16:13:44 +08:00

33. 这个最好也是用表来展示  
   - YUN PENG | 2026-04-29 16:14:20 +08:00

34. 这个为啥要框起来highlight？  
   - YUN PENG | 2026-04-29 16:17:32 +08:00

35. 这个你可以在后面单独加一section：discussion来讨论这些  
   - YUN PENG | 2026-04-29 16:18:03 +08:00

## Page 6

36. 你这个表是在哪提到的？没有看到reference的地方  
   - YUN PENG | 2026-04-29 16:21:29 +08:00

37. 你这起手上来就finding有点离谱，多写一点观察和发现再写findings，你可以把前面怎么做agreement的搬到这里来  
   - YUN PENG | 2026-04-29 16:22:27 +08:00

38. 要cite，有self-alignment bias的paper  
   - YUN PENG | 2026-04-29 16:23:31 +08:00

## Page 7

39. 这个也是，不要起手finding，这个的数据在哪？  
   - YUN PENG | 2026-04-29 16:25:40 +08:00

40. 啥叫CSV-derived？  
   - YUN PENG | 2026-04-29 16:26:26 +08:00

41. 为啥选2,以及1-5分的评分标准前面好像也没有讲  
   - YUN PENG | 2026-04-29 16:26:57 +08:00

## Page 8

42. 如果一个点很小的话，建议直接加粗成一个小点，不需要写成一个subsection，我发现现在很多这种很小的subsection  
   - YUN PENG | 2026-04-29 16:28:44 +08:00

43. case study一般是要有图片或者例子的  
   - YUN PENG | 2026-04-29 16:30:06 +08:00

44. 这个不能算是一个finding吧，这只是你的policy的motivation，finding是客观描述实验结果的  
   - YUN PENG | 2026-04-29 16:30:28 +08:00

45. 这个看起来像是一个implication，就是你从finding里面总结出来的经验，如果是implication不是具体的方法的话，我是建议不要作为main contribution大写特写，因为你这个也没有验证过，写一个小点提一下总结了这些policy就行。  
   - YUN PENG | 2026-04-29 16:31:59 +08:00

46. 涉及到公司相关claim的都要慎重，如果公司没用但是你claim用了容易产生合规风险，而且有些属于公司内部的决策，不应该告诉外界的也不应该透露。  
   - YUN PENG | 2026-04-29 16:34:18 +08:00

## Page 9

47. Threats to validity只有三类：internal, external和construct，你要把所有的这里列的都分到这三类里面去，然后只有这三个subsection  
   - YUN PENG | 2026-04-29 16:31:04 +08:00

48. 这个图片干啥的，没有地方reference它  
   - YUN PENG | 2026-04-29 16:33:57 +08:00

49. 这个最好不要当成main contribution，主要的贡献还是empirical study和总结的findings，核心就是coding agents还搞不定现在的工业级开发  
   - YUN PENG | 2026-04-29 16:35:09 +08:00

## Page 10

50. 这个不需要写这么多，你就说你的replication package在哪就行，一句话。  
   - YUN PENG | 2026-04-29 16:29:24 +08:00

51. 这个有点像你的limitation而不是future work，future work应该是类似于可以从哪些方面去改进现在的coding agents  
   - YUN PENG | 2026-04-29 16:36:00 +08:00

## Page 12

52. reference也不能超过2页，注意  
   - YUN PENG | 2026-04-29 16:36:39 +08:00
