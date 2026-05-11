# Data Analyst Project

## Architecture
- **LangGraph StateGraph** workflow orchestration (graph.py)
- **Shared state**: DataAnalysisState (TypedDict in state.py) passed between nodes
- **Nodes**: supervisor → {loader, cleaner, eda, viz, ml, reporter} → supervisor → ...
- **Base class**: BaseAgent in agents/base.py — LLM call → code gen → sandbox execution pattern

## Agent Flow
1. `supervisor` (LLM routing) → decides next agent
2. Each agent inherits BaseAgent, implements: system_prompt, build_user_prompt, parse_result
3. BaseAgent.run() calls LLM → extracts python code blocks → executes in sandbox (subprocess)

## State Fields (DataAnalysisState)
- data: file_path, dataframe_json, data_info, column_names, row_count, column_count, dtypes
- analysis: user_query, current_task, analysis_plan, completed_steps
- code execution: last_code, last_output, code_history (list[dict])
- visualizations: figure_paths (list[str])
- ml: ml_models, feature_importance
- report: report (markdown string)
- control: next_agent, loop_count, error

## Key Files
- `config.py` — All tunable params (LLM model, timeouts, limits via env vars)
- `state.py` — DataAnalysisState TypedDict
- `graph.py` — StateGraph build + run_analysis() entry point
- `agents/base.py` — BaseAgent (LLM call, code extraction, sandbox execution, error handling)
- `agents/supervisor.py` — LLM router that decides next agent
- `agents/data_loader.py` — File loading agent
- `agents/data_cleaner.py` — Data cleaning agent
- `agents/eda.py` — Exploratory data analysis
- `agents/visualization.py` — Chart generation
- `agents/ml_agent.py` — ML modeling
- `agents/reporter.py` — Markdown report generation
- `tools/code_executor.py` — CodeExecutor: AST safety check → subprocess run → output capture
- `tools/file_handler.py` — File I/O utilities
- `eval/` — Offline evaluation framework

## Code Execution (CodeExecutor)
- Safety: AST-based forbidden imports/calls check (subprocess, os.system, eval, etc.)
- Subprocess with timeout (CODE_TIMEOUT_SEC, default 60s)
- Preamble + user code + inter-agent persistence (auto-saves df as pickle)
- Figure path collection after execution
- Working directory: sandbox/
- Output truncated at CODE_MAX_OUTPUT_LINES (default 200)

## Environment
- Python 3.14
- pip dependencies installed system-wide or in venv/
- Key deps: langchain-openai, langgraph, pandas, numpy, matplotlib, seaborn, scikit-learn, openpyxl

## Multi-Task Pipeline (pipeline.py)

`pipeline.py` — 多任务调度器，支持在多个终端并行跑多个数据分析任务。

### 多终端模式（每个终端跑一个独立任务）
```bash
# 终端 1
python pipeline.py run --task-id sales_q1 --file data/sales_q1.csv --query "分析第一季度销售趋势"

# 终端 2
python pipeline.py run --task-id sales_q2 --file data/sales_q2.csv --query "分析第二季度销售趋势"
```

### 批量模式（一个终端并行跑多个）
```bash
# 准备 tasks.json:
# [{"task_id":"t1","file":"d1.csv","query":"分析A"},{"task_id":"t2","file":"d2.csv","query":"分析B"}]

python pipeline.py tasks.json --concurrent 3
```

### 任务隔离机制
- 每个任务通过 `ProcessPoolExecutor` 在独立子进程中执行
- 每个任务有独立的 sandbox 子目录: `analysis_results/<task_id>/sandbox/`
- 互不干扰：_working_data.pkl、figure、self_inspect 均在各自目录下
- 结果保存: `analysis_results/<task_id>/report.md`

### Pipeline 核心
- `AnalysisTask` — 任务定义（task_id, file_path, user_query, output_dir）
- `_run_single_task()` — 子进程执行函数（隔离 sandbox 环境）
- `PipelineScheduler` — 调度器（ProcessPoolExecutor + as_completed 进度输出）

## Task: Add Self-Inspection / Post-Mortem System

Add a self-inspection system that:
1. Records runtime issues during each analysis execution (slow execution, code failures, data loading errors, logic issues, etc.)
2. After the workflow finishes, automatically analyzes all recorded issues and generates optimization suggestions
3. Saves the analysis report to a persistent file (e.g., `self_inspect/report_<timestamp>.md`)
4. Saves accumulated data in `self_inspect/history.jsonl` for trend analysis over time

This should be a lightweight, non-intrusive system:
- A new module `self_inspect.py` at project root
- A new state field `inspection_log: list[dict]` added to DataAnalysisState
- Instrument the BaseAgent.run() and graph.py run_analysis() to log issues
- After the full workflow, call a post-mortem analyzer (LLM-based) to review the log
- The auto-saved optimization report should be referenced in the final analysis report
