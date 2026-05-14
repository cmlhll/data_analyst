"""
State 定义 —— LangGraph 多 Agent 共享状态的 TypedDict。

每个 Agent 节点读取 state 中的相关字段，执行分析后写回。
"""

from typing import TypedDict, Annotated, Sequence, Optional, Any
from langchain_core.messages import BaseMessage
import operator


class DataAnalysisState(TypedDict):
    """
    LangGraph 共享状态。

    ── 消息流 ──
    messages:       Annotated[list, operator.add] — 全局消息日志（累加）

    ── 数据层 ──
    file_path:      str   — 用户上传/指定的数据文件路径
    dataframe_json: str   — 当前数据 df 的 JSON 序列化快照（最大 1000 行）
    data_info:      str   — df.info() / df.describe() 文本摘要
    column_names:   list[str] — 列名
    row_count:      int
    column_count:   int
    dtypes:         dict  — {col: dtype}

    ── 分析上下文 ──
    user_query:     str                 — 用户原始问题
    current_task:   str                 — 当前 Agent 执行的任务描述
    analysis_plan:  list[str]           — 分析步骤计划
    completed_steps: list[str]          — 已完成步骤

    ── 代码执行 ──
    last_code:      str                 — 最近执行的代码
    last_output:    str                 — 最近执行的 stdout/stderr
    code_history:   list[dict]          — [{"code": ..., "output": ..., "agent": ...}, ...]

    ── 可视化 ──
    figure_paths:   list[str]           — 已保存图表文件路径

    ── 模型结果 ──
    ml_models:      dict                — {name: {model_obj, metrics, ...}}
    feature_importance: dict            — {feature: score}

    ── 最终报告 ──
    report:         str                 — 最终分析报告（Markdown）

    ── 流程控制 ──
    next_agent:     str                 — Supervisor 决定的下一个 Agent 名称
    loop_count:     int                 — 工作流循环计数器
    error:          Optional[str]       — 当前错误信息
    """
    # 消息
    messages: Annotated[Sequence[BaseMessage], operator.add]

    # 数据
    file_path: str
    dataframe_json: str
    data_info: str
    column_names: list[str]
    row_count: int
    column_count: int
    dtypes: dict

    # 分析上下文
    user_query: str
    current_task: str
    analysis_plan: list[str]
    completed_steps: list[str]

    # 代码执行
    last_code: str
    last_output: str
    code_history: list[dict]

    # 可视化
    figure_paths: list[str]

    # 模型
    ml_models: dict
    feature_importance: dict

    # 报告
    report: str

    # 控制
    next_agent: str
    loop_count: int
    error: Optional[str]

    # 自检
    inspection_log: list[dict]
    inspection_report: str

    # 数据集模式
    dataset_dir: str
    metadata_content: str
    data_tables: dict
    mode: str  # 'file' or 'dataset'
