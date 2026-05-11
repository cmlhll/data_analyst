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
