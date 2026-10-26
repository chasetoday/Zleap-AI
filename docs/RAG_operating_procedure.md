# 词法检索 RAG V0.1｜运行说明

## 运行流程

`两份模拟制度文件 -> 按章节拆分为15个可引用的片段 -> 中文字符二元组BM25排名 -> top-k片段 -> Qwen API -> 带证据的回答 -> 保存检索过程和模型原文`

只有命中片段进入模型上下文，未检索到的正文不会直接提供给模型。该实现**没有embedding、向量库或reranker**。

## Windows运行（项目根目录CMD）

只检索，不收费：

```cmd
python scripts\06_run_rag.py --dry-run --start-case TC009 --limit 1 --top-k 5
```

真实调用一个案例（收费）：

```cmd
python scripts\06_run_rag.py --run --start-case TC009 --limit 1 --top-k 5
```

真实调用30个案例（先核实预算和检索设置）：

```cmd
python scripts\06_run_rag.py --run --start-case TC005 --limit 30 --top-k 5
```


## 评测边界

- 先检查每道题 **retrieved_chunks** 是否包含支持参考答案的关键章节，再判断生成回答。检索漏掉证据，与模型读取了证据却答错，属于不同错误。
- 所有模型评分必须复核；不能复制原先全文上下文30题的分数作为RAG结果。
- `top-k=5` 是根据这份开发集检查后选的检索设置，不是独立验证集调参结论。
- 一旦测试集/KB/模型/检索策略改变，单独记录新的实验版本，保留原始日志，不覆盖。
