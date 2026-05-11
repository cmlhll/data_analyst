# Data Analyst — 多智能体数据分析系统

参考 ChatGPT Advanced Data Analysis 设计，基于 **LangGraph** 实现的多智能体协作数据分析系统。

[![GitHub](https://img.shields.io/badge/GitHub-cmlhll/data__analyst-181717?logo=github)](https://github.com/cmlhll/data_analyst)

## 架构

```
┌────────────────────────────────────────────┐
│                Supervisor                  │  ← 任务路由器 (LLM 决策)
│                  (路由器)                    │
└───────┬───────┬───────┬───────┬───────┬────┘
        │       │       │       │       │
   ┌────┐  ┌────┐  ┌────┐  ┌────┐  ┌────┐  ┌────────┐
   │Loader│ │Cleaner│ │EDA │  │Viz │  │ ML │  │Reporter│
   │数据加载│ │数据清洗│ │探索│  │可视化│  │建模│  │ 报告   │
   └────┘  └────┘  └────┘  └────┘  └────┘  └────────┘
        │       │       │       │       │       │
        └───────┴───────┴───────┴───────┴───────┘
                        │
                 回到 Supervisor（循环决策）
```

### 7 个专业 Agent

| Agent | 职责 |
|-------|------|
| **Supervisor** | 读取分析进度，LLM 决策下一个执行的专业 Agent |
| **DataLoader** | 加载 CSV/Excel/JSON/Parquet/TSV，生成数据摘要 |
| **DataCleaner** | 缺失值处理、异常值检测、类型转换、去重 |
| **EDA** | 描述统计、分布分析、相关性矩阵、洞察提取 |
| **Visualization** | matplotlib/seaborn 图表：柱状图、散点图、热力图、箱线图等 |
| **ML Agent** | 特征工程、模型训练（分类/回归/聚类）、交叉验证与评估 |
| **Reporter** | 汇总所有分析结果，生成结构化 Markdown 报告 |

---

## 快速开始

### 1. 安装依赖

```bash
cd data_analyst
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置 LLM

```bash
export OPENAI_API_KEY="sk-..."
# 可选配置
export DATA_ANALYST_MODEL="gpt-4o"
export DATA_ANALYST_TEMPERATURE="0.1"
```

### 3. 运行分析

```bash
source venv/bin/activate

# 基础分析
python main.py data/sales.csv

# 指定分析需求
python main.py data/iris.csv --query "分析品种分类特征，训练分类模型并可视化"

# 多轮对话（同一会话续问）
python main.py data/orders.csv --thread-id session-001
```

---

## 🏃 多任务调度（Pipeline）

支持在多个终端中并行执行多个数据分析任务，每个任务在独立子进程中运行。

### 多终端模式（每个终端跑一个任务）

```bash
# 终端 1
python pipeline.py run --task-id sales_q1 --file data/sales_q1.csv --query "分析第一季度销售趋势"

# 终端 2
python pipeline.py run --task-id sales_q2 --file data/sales_q2.csv --query "分析第二季度销售趋势"
```

### 批量模式（一个终端并行跑多个）

```bash
# 准备 tasks.json
cat > tasks.json << 'EOF'
[
  {"task_id": "sales", "file": "data/sales.csv", "query": "分析销售趋势"},
  {"task_id": "users", "file": "data/users.csv", "query": "分析用户行为"}
]
EOF

# 并发执行（--concurrent 指定并行数）
python pipeline.py tasks.json --concurrent 3

# 或直接内联传 JSON
python pipeline.py --inline '[{"task_id":"demo","file":"data/demo.csv","query":"分析"}]'
```

### 查看历史结果

```bash
python pipeline.py results
```

每个任务的结果保存在 `analysis_results/<task_id>/` 目录下，包含：
- `report.md` — 最终分析报告
- `figures/` — 生成的图表
- `self_inspect/` — 自检报告
- `_summary.json` — 执行摘要
- `_error.log` — 错误日志（如有）

---

## 🔍 自检系统

每次分析执行时自动记录运行过程中的问题，并在流程结束后生成优化报告。

### 自动检测的问题类型

| 问题分类 | 严重程度 | 触发条件 |
|---------|---------|---------|
| `CODE_FAILURE` | HIGH | 沙箱代码执行失败 |
| `EXECUTION_SLOW` | MEDIUM/HIGH | 执行耗时超过阈值（默认 30s） |
| `MEMORY_HIGH` | HIGH | 输出包含内存错误关键词 |
| `DATA_LOAD_ERROR` | HIGH | DataLoader 阶段执行失败 |
| `UNEXPECTED_NULL` | LOW | EDA/Cleaner 发现大量空值 |

### 输出

- `self_inspect/history.jsonl` — 累积的问题记录（可做趋势分析）
- `self_inspect/report_<session>_<timestamp>.md` — 每次运行的优化报告

自检报告包含：概览统计 → 问题明细（按严重程度排序）→ 优化建议 → 长期改进方向。
通过 `config.py` 中的 `SLOW_EXECUTION_THRESHOLD_MS` 可调整慢执行检测阈值。

---

## 📊 离线评测

项目内置 `eval/` 子系统，用于评估"用户上传文件 + 自然语言问题"的数据分析效果。

```bash
# mock 模式（不调用 LLM，快速验证评测链路）
python -m eval.run_eval

# 真实 Agent 模式（跑完整 LangGraph 工作流）
python -m eval.run_eval --mode agent
```

评测自动生成合成数据集，输出到：
- `eval/generated_data/` — 自动生成的 CSV 与 cases.json
- `eval/results/` — 评测明细与 Markdown 报告

当前覆盖能力：文件读取、数据质量、EDA、异常识别、可视化、建模、执行成功率和报告关键词覆盖。

---

## 项目结构

```
data_analyst/
├── main.py                 # CLI 入口（单任务）
├── pipeline.py             # 多任务调度器（多终端并行）
├── graph.py                # LangGraph 工作流编排
├── state.py                # 共享状态 TypedDict
├── config.py               # 全局配置（LLM、超时、路径等）
├── self_inspect.py         # 自检系统（问题记录 + 事后分析）
├── requirements.txt
├── agents/
│   ├── base.py             # Agent 基类（LLM 调用 + 代码执行 + 自检注入）
│   ├── supervisor.py       # 任务路由器
│   ├── data_loader.py      # 数据加载
│   ├── data_cleaner.py     # 数据清洗
│   ├── eda.py              # 探索性分析
│   ├── visualization.py    # 数据可视化
│   ├── ml_agent.py         # 机器学习
│   └── reporter.py         # 报告生成
├── tools/
│   ├── code_executor.py    # 代码沙箱（子进程 + AST 安全校验 + 超时）
│   └── file_handler.py     # 文件上传/解析/校验
├── eval/                   # 离线评测集、runner、scorers
├── sandbox/                # 代码执行临时目录（自动创建）
├── figures/                # 图表输出目录（自动创建）
├── self_inspect/           # 自检报告目录（自动创建）
└── analysis_results/       # 多任务调度结果目录（自动创建）
```

## 设计要点

- **LangGraph StateGraph**：所有 Agent 共享 `DataAnalysisState`，通过 Supervisor 条件路由实现动态工作流
- **代码沙箱**：LLM 生成 Python 代码 → AST 安全检查 → 子进程执行 → 捕获 stdout/stderr/图表
- **可重入**：MemorySaver 检查点支持多轮对话和断点续传
- **Agent 间数据持久化**：每个 Agent 修改后的 df 自动保存为 pickle，传递给后续 Agent
- **路径安全**：所有 Agent 访问的文件路径都经过项目根目录校验，防止路径遍历攻击
- **自检注入**：BaseAgent 基类统一注入执行时序监控和问题检测，无需修改子 Agent
- **任务隔离**：多任务调度通过 ProcessPoolExecutor 实现，每个任务在独立进程 + 独立目录中运行
