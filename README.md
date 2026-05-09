# Data Analyst — 多智能体数据分析系统

参考 ChatGPT Advanced Data Analysis 设计，基于 **LangGraph** 实现的多智能体协作数据分析系统。

## 架构

```
                    ┌─────────────┐
                    │  Supervisor │  ← 任务路由器
                    │  (路由器)     │
                    └──────┬──────┘
           ┌───────┬───────┼───────┬───────┬───────┐
           ▼       ▼       ▼       ▼       ▼       ▼
      ┌────────┐┌──────┐┌────┐┌────────┐┌──────┐┌────────┐
      │ Loader ││Cleaner││EDA ││  Viz   ││  ML  ││Reporter│
      │ 数据加载││数据清洗││探索 ││ 可视化  ││ 建模 ││ 报告   │
      └────────┘└──────┘└────┘└────────┘└──────┘└────────┘
           │       │       │       │       │       │
           └───────┴───────┴───────┴───────┴───────┘
                            │
                       回到 Supervisor（循环决策）
```

## 7 个专业 Agent

| Agent | 职责 |
|-------|------|
| **Supervisor** | 读取分析进度，决策下一个执行的专业 Agent |
| **DataLoader** | 加载 CSV/Excel/JSON/Parquet，生成数据摘要 |
| **DataCleaner** | 缺失值处理、异常值检测、类型转换、去重 |
| **EDA** | 描述统计、分布分析、相关性矩阵、洞察提取 |
| **Visualization** | matplotlib/seaborn 图表：柱状图、散点图、热力图、箱线图等 |
| **ML Agent** | 特征工程、模型训练（分类/回归/聚类）、交叉验证与评估 |
| **Reporter** | 汇总所有分析结果，生成结构化 Markdown 报告 |

## 快速开始

### 1. 创建虚拟环境并安装依赖

```bash
cd data_analyst

# macOS 系统 Python 受保护，必须先创建 venv
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

### 2. 配置 LLM

```bash
export OPENAI_API_KEY="sk-..."
# 可选：自定义模型
export DATA_ANALYST_MODEL="gpt-4o"
export DATA_ANALYST_TEMPERATURE="0.1"
```

### 3. 运行分析

```bash
# 确保 venv 已激活
source venv/bin/activate

# 基础分析
python main.py data/sales.csv

# 指定分析需求
python main.py data/iris.csv --query "分析品种分类特征，训练分类模型并可视化"

# 多轮对话
python main.py data/orders.csv --thread-id session-001
```

## 离线评测

项目内置 `eval/` 子系统，用于评估“用户上传文件 + 自然语言问题”的数据分析效果。

```bash
# mock 模式：不调用 LLM，适合 CI 或快速验证评测链路
python -m eval.run_eval

# 真实 Agent 模式：通过 graph.run_analysis 跑完整 LangGraph 工作流
python -m eval.run_eval --mode agent
```

评测会自动生成小型合成数据集，并输出：

```text
eval/generated_data/      # 自动生成的 CSV 与 cases.json
eval/results/             # 评测明细与 Markdown 报告
```

当前覆盖能力：文件读取、数据质量、EDA、异常识别、可视化、建模、执行成功率和报告关键词覆盖。

## 项目结构

```
data_analyst/
├── main.py                 # CLI 入口
├── graph.py                # LangGraph 工作流编排
├── state.py                # 共享状态 TypedDict
├── config.py               # 全局配置
├── requirements.txt
├── agents/
│   ├── __init__.py
│   ├── base.py             # Agent 基类（LLM 调用 + 代码执行）
│   ├── supervisor.py       # 任务路由器
│   ├── data_loader.py      # 数据加载
│   ├── data_cleaner.py     # 数据清洗
│   ├── eda.py              # 探索性分析
│   ├── visualization.py    # 数据可视化
│   ├── ml_agent.py         # 机器学习
│   └── reporter.py         # 报告生成
├── tools/
│   ├── __init__.py
│   ├── code_executor.py    # 代码沙箱（子进程执行 + 超时控制）
│   └── file_handler.py     # 文件上传/解析/校验
├── eval/                   # 离线评测集、runner、scorers
├── sandbox/                # 代码执行临时目录（自动创建）
└── figures/                # 图表输出目录（自动创建）
```

## 设计要点

- **LangGraph StateGraph**：所有 Agent 共享 `DataAnalysisState`，通过 Supervisor 条件路由实现动态工作流
- **代码沙箱**：LLM 生成 Python 代码 → 子进程执行（超时 60s）→ 捕获 stdout/stderr/图表
- **可重入**：MemorySaver 检查点支持多轮对话和断点续传
- **幂等路由**：Supervisor 基于 `analysis_plan` + `completed_steps` 决定下一步，不会重复执行已完成的步骤
- **离线评测**：`eval/` 通过 mock 模式和真实 Agent 模式评估报告质量、执行轨迹和关键能力覆盖
