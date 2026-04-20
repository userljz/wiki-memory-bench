# Wiki-Memory-Bench

面向 LLM Agent 的 Markdown / Wiki 风格长期记忆系统基准与评测框架。

## 为什么要做这个项目
大多数 memory benchmark 关注的是通用检索、上下文拼接，或者 agent runtime 行为。这些方向当然有价值，但它们没有充分覆盖一类越来越常见的系统：

- 本地 Markdown 记忆库
- wiki 风格的持久记忆
- 人工挑选的记忆片段，而不是整段原始日志
- 不只是检索，还包括更新与维护工作流

`wiki-memory-bench` 的目标，就是直接评测这类系统。它不只关心系统能不能答对问题，也关心系统能不能长期维护一个真正有用的记忆载体：

- 它保存了什么
- 它更新了什么
- 它把什么标记为过时
- 它忘掉了什么
- 它引用了什么

## 它有什么不同
这个项目的差异化主要来自四个设计点。

### Markdown / Wiki 记忆系统
项目聚焦的是把记忆编译成 Markdown 文件或 wiki 页面这类系统，而不只是向量库或黑盒 agent state。

### 人工精选 clips
基准显式支持 curated memory input，也就是“人类真正会选择保存下来”的 clips 或 sessions，而不只是整段原始对话。

### update / stale / citation 指标
这个 harness 跟踪的不只是 answer accuracy。它专门衡量：

- 更新和知识变更
- stale claim 处理
- citation 质量
- forgetting 行为
- wiki artifact 大小与检索成本

### 可复现的评测框架
整个系统是 local-first、可脚本化、可复现的：

- `uv`
- Typer CLI
- JSONL prepared data
- 保存在 `runs/` 下的 run artifacts
- 默认 deterministic baselines
- 需要时可启用基于 LiteLLM 的 answerer 和 judge

默认 quickstart 不需要任何 API key。

## 快速开始
### 安装

```bash
uv sync
uv run wmb datasets list
uv run wmb systems list
```

### 运行 synthetic wiki-memory benchmark

```bash
uv run wmb synthetic generate --cases 100 --out data/synthetic/wiki_memory_100.jsonl
uv run wmb run --dataset synthetic-wiki-memory --system clipwiki --limit 50
uv run wmb report runs/latest
```

### 实验性外部 adapter：Basic Memory

```bash
uv tool install basic-memory
uv run wmb systems doctor basic-memory
uv run wmb run --dataset synthetic-wiki-memory --system basic-memory --limit 20
```

### 运行 LoCoMo-MC10 benchmark

```bash
uv run wmb datasets prepare locomo-mc10 --limit 20
uv run wmb run --dataset locomo-mc10 --system bm25 --limit 20
uv run wmb run --dataset locomo-mc10 --system vector-rag --limit 20
uv run wmb run --dataset locomo-mc10 --system clipwiki --mode oracle-curated --limit 20
uv run wmb report runs/latest
```

### 可选的 LLM answerer / judge

```bash
export LLM_MODEL="openai/gpt-4o-mini"
export LLM_API_KEY="your-api-key"
# 可选：OpenRouter 或本地 OpenAI-compatible 服务
export LLM_BASE_URL="http://localhost:8000/v1"

uv run wmb run --dataset locomo-mc10 --system clipwiki --answerer llm --judge llm --limit 20
uv run wmb report runs/latest --show-prompts
```

### 运行 LongMemEval-cleaned benchmark

```bash
uv run wmb datasets prepare longmemeval --split s --limit 20
uv run wmb run --dataset longmemeval-s --system bm25 --limit 20
uv run wmb run --dataset longmemeval-s --system clipwiki --mode full-wiki --limit 20
uv run wmb report runs/latest
```

## 示例输出表
下面是可复现的 v0.1-alpha 示例结果。完整结果见 [`reports/v0.1-alpha-results.md`](reports/v0.1-alpha-results.md)，由 [`scripts/reproduce_v0_1_alpha.sh`](scripts/reproduce_v0_1_alpha.sh) 自动生成。

| 数据集 | 系统 | 模式 | Answerer | Accuracy | Avg Retrieved Tokens | Avg Latency |
| --- | --- | --- | --- | ---: | ---: | ---: |
| `synthetic-mini` | `bm25` | default | deterministic | 100.00% | 37.40 | 0.11 ms |
| `synthetic-wiki-memory` | `bm25` | default | deterministic | 50.00% | 41.94 | 0.04 ms |
| `synthetic-wiki-memory` | `clipwiki` | default | deterministic | 10.00% | 202.16 | 16.87 ms |
| `locomo-mc10` | `bm25` | default | deterministic | 28.00% | 2189.48 | 3.13 ms |
| `locomo-mc10` | `vector-rag` | default | deterministic | 22.00% | 765.40 | 870.27 ms |
| `locomo-mc10` | `clipwiki` | `full-wiki` | deterministic | 32.00% | 3447.58 | 88.00 ms |

## 已支持的数据集
| 数据集别名 | 任务类型 | 状态 | 说明 |
| --- | --- | --- | --- |
| `synthetic-mini` | multiple-choice | stable | 内置 smoke suite，适合快速 sanity check |
| `synthetic-wiki-memory` | open QA diagnostics | stable | 确定性生成的 wiki-memory maintenance 诊断任务 |
| `locomo-mc10` | 10-choice QA | stable | 对接 `Percena/locomo-mc10` |
| `longmemeval-s` | open QA | stable | 首个支持的 `LongMemEval-cleaned` split |
| `longmemeval-m` | open QA | experimental | 更大、更慢的 split |
| `longmemeval-oracle` | open QA | experimental | oracle retrieval 子集 |
| `longmemeval` | prepare alias | stable | prepare 时通过 `--split s|m|oracle` 选择 |

数据集准备命令：

```bash
uv run wmb datasets prepare locomo-mc10 --limit 20
uv run wmb datasets prepare longmemeval --split s --limit 20
uv run wmb datasets prepare longmemeval --split m --sample 50
```

## 已支持的记忆系统
| 系统 | 检索单元 | Answerer 模式 | 说明 |
| --- | --- | --- | --- |
| `full-context-oracle` | full history | deterministic, llm | sanity upper bound；deterministic 模式直接使用 gold choice，不应当作公平的可部署 baseline |
| `full-context-heuristic` | full history | deterministic, llm | 非 oracle 的 full-context heuristic，使用和其他检索基线同一类 deterministic answerer |
| `bm25` | lexical session documents | deterministic, llm | 成本低、完全本地的检索 baseline |
| `vector-rag` | embedding-based session chunks | deterministic, llm | 使用 `sentence-transformers` 的内存向量索引 |
| `clipwiki` | compiled wiki pages | deterministic, llm | 确定性 Markdown wiki baseline，支持 `oracle-curated`、`full-wiki`、`noisy-curated` |

兼容性说明：

- `full-context` 目前保留为 `full-context-oracle` 的向后兼容别名

`full-context-oracle` 可以作为 sanity upper bound 使用，但**不应**直接和真实 retrieval / memory system baseline 做公平对比。

## 实验性外部 Adapters
当前的实验性外部 adapter：

- `basic-memory`

重要说明：

- 如果本机没有安装 Basic Memory CLI，这个 adapter 会自动回退到本地 lexical search
- 这种 fallback mode 适合 smoke test 和 adapter 开发
- 但它**不应**被视为“真实的 Basic Memory benchmark 结果”
- fallback mode 下的 Basic Memory 结果**不应**放入 README 主结果表

请始终先运行：

```bash
uv run wmb systems doctor basic-memory
```

确认当前运行的是：

- `real_basic_memory`
- `fallback_local_search`

如果你想跑真实 integration tests：

```bash
export WMB_RUN_BASIC_MEMORY_INTEGRATION=1
uv run pytest tests/test_basic_memory.py
```

`vector-rag` 默认配置：

- embedding model: `sentence-transformers/all-MiniLM-L6-v2`
- 可通过 `WMB_VECTOR_RAG_MODEL` 覆盖
- 可通过 `WMB_VECTOR_RAG_TOP_K` 覆盖检索深度

## 架构

```mermaid
flowchart LR
    rawData[RawDatasetsAndSyntheticTemplates] --> prepareCli[DatasetPrepareCLI]
    prepareCli --> preparedCases[PreparedEvalCases]
    preparedCases --> adapters[MemorySystemAdapters]
    adapters --> artifacts[PredictionsRetrievalAndWikiArtifacts]
    artifacts --> metrics[DeterministicMetricsAndOptionalLLMJudge]
    metrics --> runStore[RunStore]
    runStore --> reportCli[RichCLIReport]
```

这个项目最重要的契约很简单：

1. 把所有数据集规范化到统一 case schema
2. 让所有 memory system 走同一套 adapter 接口
3. 从保存下来的 artifacts 评分，而不是依赖临时 prompt 日志

## 如何添加新的 memory system adapter
简要流程：

1. 在 `src/wiki_memory_bench/systems/` 下新增模块
2. 继承 `SystemAdapter`
3. 实现 `run()`，必要时实现 `prepare_run()` / `finalize_run()`
4. 返回 `SystemResult`
5. 用 `@register_system` 注册
6. 添加测试和 CLI smoke 路径

最小结构如下：

```python
@register_system
class MyMemorySystem(SystemAdapter):
    name = "my-memory-system"
    description = "Short description."

    def prepare_run(self, run_dir: Path, dataset_name: str) -> None:
        ...

    def run(self, example: PreparedExample) -> SystemResult:
        ...
```

完整清单、artifact 约定和测试建议见 `docs/adapter-guide.md`。

## 如何添加新的数据集
简要流程：

1. 在 `src/wiki_memory_bench/datasets/` 下新增模块
2. 继承 `DatasetAdapter`
3. 把原始记录转换成 `EvalCase`
4. 尽可能保留 timestamps、evidence metadata 和 source references
5. 用 `@register_dataset` 注册
6. 添加 fixture 驱动的测试和 CLI prepare smoke test

最小结构如下：

```python
@register_dataset
class MyDataset(DatasetAdapter):
    name = "my-dataset"
    description = "Short description."

    def load(self, limit: int | None = None, sample: int | None = None) -> PreparedDataset:
        ...
```

规范化 schema、split 处理和 fixture 策略见 `docs/dataset-guide.md`。

## 路线图
近期优先级：

- 加强 `LongMemEval` 上的 deterministic open-QA answer extraction
- 增加 `markdown-summary` baseline
- 改进 evidence-aware citation coverage 指标
- 增加更强的 synthetic maintenance 和 patch correctness 评测
- 更系统地 benchmark `longmemeval-m` 和 `longmemeval-oracle`
- 改进 `clipwiki` 在 update / stale claim 上的编译启发式

后续扩展方向：

- 外部 adapter：`basic-memory`、`agentmemory`、`llm-wiki-skill`、`Mem0`、`Zep`
- 更丰富的 report 导出和可发表的实验表格
- 基于 `docs/technical-report-outline.md` 的正式技术报告

## Citation / Acknowledgements
如果你在研究或产品评测中使用这个仓库，在正式技术报告或 DOI 发布之前，请至少引用仓库 URL 和具体 commit。

相关数据集、memory systems 和关键基础库的致谢见 `ACKNOWLEDGEMENTS.md`。

相关设计与规划文档：

- `docs/research-notes.md`
- `docs/architecture.md`
- `docs/dataset-strategy.md`
- `docs/mvp-plan.md`
- `docs/non-goals.md`
- `docs/technical-report-outline.md`
- `docs/adapter-guide.md`
- `docs/basic-memory-adapter.md`
- `docs/dataset-guide.md`

## License
当前仓库还没有最终确定的根级 `LICENSE` 文件。

在公开发布之前，建议补上正式许可证，并确认它与以下内容兼容：

- 这个代码库的预期使用方式
- 被 benchmark 的公开数据集的 license / 使用条款
- 未来下游再分发的计划

数据集层面的 license 细节请参考 `ACKNOWLEDGEMENTS.md` 和各自的 dataset card。
