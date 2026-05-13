"""
LangGraph 工作流编排 —— StateGraph 构建 + 条件路由。

流程：
START → supervisor → {loader, cleaner, eda, viz, ml, reporter}
                   → supervisor → ... → reporter → FINISH
"""
import logging

from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from state import DataAnalysisState
from agents.supervisor import SupervisorAgent
from agents.data_loader import DataLoaderAgent
from agents.data_cleaner import DataCleanerAgent
from agents.eda import EDAAgent
from agents.visualization import VisualizationAgent
from agents.ml_agent import MLAgent
from agents.reporter import ReporterAgent
from self_inspect import PostMortemAnalyzer
import config

logger = logging.getLogger(__name__)


# ── 构建节点 ───────────────────────────────────────────────

def supervisor_node(state: DataAnalysisState) -> dict:
    """Supervisor 路由节点。"""
    agent = SupervisorAgent()
    result = agent.run(state)
    result["loop_count"] = state.get("loop_count", 0) + 1
    return result


def data_loader_node(state: DataAnalysisState) -> dict:
    """数据加载节点。"""
    agent = DataLoaderAgent()
    return agent.run(state)


def data_cleaner_node(state: DataAnalysisState) -> dict:
    """数据清洗节点。"""
    agent = DataCleanerAgent()
    return agent.run(state)


def eda_node(state: DataAnalysisState) -> dict:
    """EDA 节点。"""
    agent = EDAAgent()
    return agent.run(state)


def visualization_node(state: DataAnalysisState) -> dict:
    """可视化节点。"""
    agent = VisualizationAgent()
    return agent.run(state)


def ml_agent_node(state: DataAnalysisState) -> dict:
    """ML 建模节点。"""
    agent = MLAgent()
    return agent.run(state)


def reporter_node(state: DataAnalysisState) -> dict:
    """报告生成节点。"""
    agent = ReporterAgent()
    return agent.run(state)


# ── 条件路由 ───────────────────────────────────────────────

def route_after_supervisor(state: DataAnalysisState) -> Literal[
    "data_loader", "data_cleaner", "eda", "visualization", "ml_agent", "reporter", "__end__"
]:
    """根据 supervisor 的 next_agent 决定下一个节点。"""
    next_agent = state.get("next_agent", "FINISH")

    # 阻止无限循环
    if state.get("loop_count", 0) > config.MAX_WORKFLOW_LOOPS:
        return "reporter"

    if next_agent == "FINISH":
        # 如果有报告则结束，没有则先生成报告
        if state.get("report", ""):
            return END
        else:
            return "reporter"

    return next_agent


def route_after_agent(state: DataAnalysisState) -> Literal["supervisor", "__end__"]:
    """各 Agent 执行后都回到 supervisor 决策。"""
    if state.get("loop_count", 0) > config.MAX_WORKFLOW_LOOPS:
        # 超过最大循环，强制进入 reporter
        if state.get("report", ""):
            return END
        return "supervisor"  # supervisor 会路由到 reporter

    # 如果有错误且已重试多次，结束
    if state.get("error") and state.get("loop_count", 0) > config.MAX_AGENT_ITERATIONS:
        return "supervisor"

    return "supervisor"


# ── 构建图 ─────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """构建并编译 LangGraph 状态图。"""
    workflow = StateGraph(DataAnalysisState)

    # 添加节点
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("data_loader", data_loader_node)
    workflow.add_node("data_cleaner", data_cleaner_node)
    workflow.add_node("eda", eda_node)
    workflow.add_node("visualization", visualization_node)
    workflow.add_node("ml_agent", ml_agent_node)
    workflow.add_node("reporter", reporter_node)

    # 入口: supervisor
    workflow.set_entry_point("supervisor")

    # supervisor → 各 agent
    workflow.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "data_loader": "data_loader",
            "data_cleaner": "data_cleaner",
            "eda": "eda",
            "visualization": "visualization",
            "ml_agent": "ml_agent",
            "reporter": "reporter",
            END: END,
        },
    )

    # 各 agent → supervisor
    for node_name in ["data_loader", "data_cleaner", "eda", "visualization", "ml_agent"]:
        workflow.add_conditional_edges(
            node_name,
            route_after_agent,
            {"supervisor": "supervisor", END: END},
        )

    # reporter → END
    workflow.add_edge("reporter", END)

    # 编译（带内存检查点）
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)

    return app


# ── 便捷运行 ───────────────────────────────────────────────

def run_analysis(
    file_path: str,
    user_query: str = "请对这份数据进行全面的数据分析",
    thread_id: str = "default",
) -> dict:
    """
    执行端到端数据分析。

    Args:
        file_path: 数据文件路径
        user_query: 分析需求
        thread_id: 会话 ID（用于多轮对话）

    Returns:
        最终 state dict
    """
    app = build_graph()

    initial_state: DataAnalysisState = {
        # 消息
        "messages": [],
        # 数据
        "file_path": file_path,
        "dataframe_json": "",
        "data_info": "",
        "column_names": [],
        "row_count": 0,
        "column_count": 0,
        "dtypes": {},
        # 分析上下文
        "user_query": user_query,
        "current_task": "",
        "analysis_plan": [
            "加载并检查数据",
            "清洗数据",
            "探索性数据分析",
            "数据可视化",
            "生成分析报告",
        ],
        "completed_steps": [],
        # 代码执行
        "last_code": "",
        "last_output": "",
        "code_history": [],
        # 可视化
        "figure_paths": [],
        # 模型
        "ml_models": {},
        "feature_importance": {},
        # 报告
        "report": "",
        # 自检
        "inspection_log": [],
        "inspection_report": "",
        # 控制
        "next_agent": "data_loader",
        "loop_count": 0,
        "error": None,
    }

    run_cfg = {"configurable": {"thread_id": thread_id}}
    final_state = None

    logger.info("开始分析: file=%s query=%s thread=%s", file_path, user_query, thread_id)
    node_count = 0

    # 获取完整的 state snapshot（含 reducer 聚合后的所有字段）
    for event in app.stream(initial_state, run_cfg):
        for node_name, node_output in event.items():
            logger.info("节点 [%s] 完成 (第 %d 步)", node_name, node_count)
            node_count += 1
            print(f"\n{'='*60}")
            print(f"📍 节点: {node_name}")
            print(f"{'='*60}")
            if node_name == "supervisor":
                print(f"路由决策: {node_output.get('next_agent', 'N/A')}")
                if "messages" in node_output and node_output["messages"]:
                    print(node_output["messages"][-1].content)
            elif node_name == "reporter":
                print(node_output.get("report", "")[:500] + "..." if len(node_output.get("report", "")) > 500 else node_output.get("report", ""))
            else:
                output = node_output.get("last_output", "")
                print(output[:1000] if output else "无输出")
            # 从 checkpoint 获取完整的聚合 state
            final_state = app.get_state(run_cfg)
            # 展开到普通 dict 以便 eval runner 使用
            if final_state:
                final_state = dict(final_state.values)

    # ── 自检：运行结束后触发事后分析 ─────────────────────────
    if final_state is not None:
        inspection_log = final_state.get("inspection_log", [])
        if inspection_log:
            logger.info("自检: 发现 %d 个问题，正在生成优化报告...", len(inspection_log))
        else:
            logger.info("自检: 运行顺利，未发现问题")
        analyzer = PostMortemAnalyzer(session_id=thread_id)
        result = analyzer.analyze_and_save(inspection_log)

        # 将优化报告追加到最终分析报告的末尾
        existing_report = final_state.get("report", "")
        if existing_report:
            final_state["report"] = existing_report + "\n\n---\n\n" + result["report"]
        else:
            final_state["report"] = result["report"]
        final_state["inspection_report"] = result["report"]

        if result["report_path"]:
            logger.info("自检报告已保存: %s", result["report_path"])
            print(f"\n📋 自检报告已保存: {result['report_path']}")

    return final_state if final_state else {}
