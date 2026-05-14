# Data Analyst Project

## Architecture
- **LangGraph StateGraph** workflow orchestration (graph.py)
- **Shared state**: DataAnalysisState (TypedDict in state.py) passed between nodes
- **Two modes**:
  - **File mode** (legacy): `python main.py data/file.csv --query "..."` → supervisor → {loader, cleaner, eda, ...}
  - **Dataset mode** (new): `python main.py data/sales --query "..."` → data_understander → supervisor → ...
- **Base class**: BaseAgent in agents/base.py — LLM call → code gen → sandbox execution pattern

## Agent Flow
1. `data_understander` (dataset mode only) — reads metadata.md, analyzes user query, generates code to load relevant data
2. `supervisor` (LLM routing) — decides next agent
3. Each agent inherits BaseAgent, implements: system_prompt, build_user_prompt, parse_result
4. BaseAgent.run() calls LLM → extracts python code blocks → executes in sandbox (subprocess)

## State Fields (DataAnalysisState)
- data: file_path, dataframe_json, data_info, column_names, row_count, column_count, dtypes
- analysis: user_query, current_task, analysis_plan, completed_steps
- code execution: last_code, last_output, code_history (list[dict])
- visualizations: figure_paths (list[str])
- ml: ml_models, feature_importance
- report: report (markdown string)
- control: next_agent, loop_count, error
- dataset_mode: dataset_dir, metadata_content, data_tables, mode ('file'|'dataset')

## Key Files
- `config.py` — All tunable params (LLM model, timeouts, limits via env vars)
- `state.py` — DataAnalysisState TypedDict
- `graph.py` — StateGraph build + run_analysis() entry point
- `agents/base.py` — BaseAgent (LLM call, code extraction, sandbox execution, error handling)
- `agents/supervisor.py` — LLM router that decides next agent
- `agents/data_understander.py` — NEW: understands dataset metadata, generates loading code
- `agents/data_loader.py` — File loading agent (legacy file mode)
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

## Dataset Mode (New)

### metadata.md format
Datasets are in `data/<name>/` directories. Each must contain a `metadata.md`:

```markdown
# 数据库：xxx

## 1. table_name (表描述)
- 描述：表的作用
- 字段：
  - field_name (PK/FK/type): 字段描述
```

### How data_understander works
1. LLM reads metadata.md → understands table schemas + relationships
2. LLM analyzes user query → identifies which tables/columns are needed
3. Generates Python code → loads CSV files, merges/joins as needed → produces single `df`
4. Code is executed in sandbox, df saved as pickle for subsequent agents
5. Subsequent agents load from pickle in preamble (no hardcoded file loading)

### Example usage
```bash
python main.py data/sales --query "分析各城市客户消费分布和热门产品"
```

## Multi-Task Pipeline (pipeline.py)

### Dataset mode in pipeline
```bash
python pipeline.py run --task-id sales_analysis --dataset data/sales --query "分析销售额趋势"
```

### Task JSON format
```json
[
  {"task_id": "t1", "dataset_dir": "/path/to/sales", "query": "分析A"},
  {"task_id": "t2", "file": "/path/to/file.csv", "query": "分析B"}
]
```
