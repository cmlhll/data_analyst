# Data Analyst — 多智能体数据分析系统

参考 ChatGPT Advanced Data Analysis 设计，基于 **LangGraph** 实现的多智能体协作数据分析系统。

[![GitHub](https://img.shields.io/badge/GitHub-cmlhll/data__analyst-181717?logo=github)](https://github.com/cmlhll/data_analyst)

## 架构

```
|┌──────────────────────────────────────────────────────┐
|│                   Supervisor                         │  ← 任务路由器 (LLM 决策)
|│                     (路由器)                           │
|└──────┬──────┬──────┬──────┬──────┬──────┬───────────┘
|       │      │      │      │      │      │
|  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌──────────┐
|  │Under│ │Loader│ │Clean│ │EDA │ │Viz │ │ ML │ │ Reporter │
|  │stand│ │数据加载│ │数据清洗│ │探索│ │可视化│ │建模│ │  报告    │
|  │ 理解│ └────┘ └────┘ └────┘ └────┘ └────┘ └──────────┘
|  └────┘      │      │      │      │      │
|       ↑      └──────┴──────┴──────┴──────┘
|  数据集模式                │
|  专用入口           回到 Supervisor（循环决策）
```

### 8 个专业 Agent

| Agent | 模式 | 职责 |
|-------|------|------|
| **Supervisor** | 全模式 | 读取分析进度，LLM 决策下一个执行的专业 Agent |
| **DataUnderstander** 🆕 | 数据集模式 | 读取 metadata.md，理解表结构和关系，生成代码加载关联数据到 df |
| **DataLoader** | 文件模式 | 加载 CSV/Excel/JSON/Parquet/TSV 单文件，生成数据摘要 |
| **DataCleaner** | 全模式 | 缺失值处理、异常值检测、类型转换、去重 |
| **EDA** | 全模式 | 描述统计、分布分析、相关性矩阵、洞察提取 |
| **Visualization** | 全模式 | matplotlib/seaborn 图表：柱状图、散点图、热力图、箱线图等 |
| **ML Agent** | 全模式 | 特征工程、模型训练（分类/回归/聚类）、交叉验证与评估 |
| **Reporter** | 全模式 | 汇总所有分析结果，生成结构化 Markdown 报告 |

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

# ── 文件模式（单个文件）──
# 基础分析
python main.py data/sales.csv

# 指定分析需求
python main.py data/iris.csv --query "分析品种分类特征，训练分类模型并可视化"

# ── 数据集模式（多表目录）──
# 数据集模式自动检测：给目录路径即可进入数据集模式
python main.py data/sales --query "分析各城市客户消费分布和热门产品"

# 多轮对话（同一会话续问）
python main.py data/orders.csv --thread-id session-001
```

### 数据集模式详解

数据集模式适用于**多表关联场景**（如电商订单、客户、产品多个文件）。

#### 数据集结构要求

每个数据集是一个独立目录，包含：
- `metadata.md` — **必须**，描述所有表的字段、类型和外键关系
- CSV 数据文件（每表一个）

```
data/sales/
├── metadata.md                 # 表结构描述
├── sales_customers.csv         # 客户表
├── sales_products.csv          # 产品表
└── sales_orders.csv            # 订单明细表
```

#### metadata.md 格式

```markdown
# 数据库：销售数据集

## 1. customers (客户信息表)
- 描述：记录客户基本信息和分群
- 字段：
  - customer_id (PK, string): 客户唯一标识
  - city (string): 客户所在城市
  - segment (string): 客户分群

## 2. orders (订单明细表)
- 描述：每笔订单的详细信息
- 字段：
  - order_id (PK, string): 订单唯一标识
  - customer_id (FK -> customers.customer_id): 客户ID
  - revenue (float): 订单金额
```

#### 工作原理

```
用户: python main.py data/sales --query "分析客户分布"
                                        │
                          ┌─────────────┴─────────────┐
                          │  DataUnderstander Agent    │
                          │ ① 读取 metadata.md         │
                          │ ② 分析用户问题 → 确定需      │
                          │    要用哪些表/字段           │
                          │ ③ 生成加载代码               │
                          │ ④ 执行代码 → 合并成 df      │
                          └─────────────┬─────────────┘
                                        │ df 传递给后续 Agent
                          ┌─────────────┴─────────────┐
                          │     Supervisor 路由         │
                          │ → Loader/Cleaner/EDA/Viz.. │
                          └───────────────────────────┘
```

- **DataUnderstander Agent** 是数据集模式的唯一入口，完成后将 `df` 持久化到 pickle
- 后续的 Loader/Cleaner/EDA 等 Agent 自动从 pickle 加载，无需重新读取文件
- **文件模式不受影响**，仍然直接从 Supervisor 路由到 DataLoader

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

# 也支持数据集模式（使用 --dataset 替代 --file）
python pipeline.py run --task-id sales_analysis --dataset data/sales --query "分析各城市客户分布和热门产品"

# 并发执行（--concurrent 指定并行数）
python pipeline.py tasks.json --concurrent 3

# 或直接内联传 JSON（支持 file 和 dataset_dir 混用）
python pipeline.py --inline '[{"task_id":"f1","file":"data/demo.csv","query":"分析"},{"task_id":"d1","dataset_dir":"data/sales","query":"分析销售趋势"}]'
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

## ✅ TDD 测试流程（开发约束）

请遵循 `TESTING_TDD.md`：

- 业务逻辑变更：先补测试
- Bug 修复：先写复现测试
- 重构：保证测试不变
- Agent 生成代码：自动执行测试（至少 `make tdd-check`）

常用命令：

```bash
make tdd-check
make test
```

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
│   ├── data_understander.py # 🆕 数据集模式入口（读取元数据 → 生成加载代码）
│   ├── data_loader.py      # 数据加载（文件模式）
│   ├── data_cleaner.py     # 数据清洗
│   ├── eda.py              # 探索性分析
│   ├── visualization.py    # 数据可视化
│   ├── ml_agent.py         # 机器学习
│   └── reporter.py         # 报告生成
├── data/
│   └── sales/              # 🆕 示例数据集（含 metadata.md + 多表 CSV）
│       ├── metadata.md
│       ├── sales_customers.csv
│       ├── sales_products.csv
│       └── sales_orders.csv
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
