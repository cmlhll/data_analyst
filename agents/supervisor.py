"""
Supervisor Agent —— 任务路由器。

读取用户查询和分析进度，决定下一步交给哪个专业 Agent 处理。
不执行代码，仅输出路由决策。
"""

import config
import json
import re
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from .base import BaseAgent
from state import DataAnalysisState


AGENT_OPTIONS = Literal[
    "data_understander",
    "data_loader",
    "data_cleaner",
    "eda",
    "visualization",
    "ml_agent",
    "reporter",
    "FINISH",
]

ROUTING_DESCRIPTIONS = {
    "data_understander": "理解数据集元数据，根据用户问题决定加载哪些数据文件（仅数据集模式）",
    "data_loader":       "加载并检查数据文件",
    "data_cleaner":      "清洗数据（缺失值、异常值、类型转换）",
    "eda":               "探索性数据分析（统计描述、分布、相关性）",
    "visualization":     "创建可视化图表",
    "ml_agent":          "机器学习建模（特征工程、训练、评估）",
    "reporter":          "综合已有结果生成最终报告",
    "FINISH":            "分析已完成，结束工作流",
}

SUPERVISOR_SYSTEM_PROMPT = """你是数据分析主管，协调以下 Agent 完成端到端分析：

Agent 列表及何时调用：
- data_understander: 数据集模式下的第一步，理解元数据并加载数据（先于 data_loader）
- data_loader:   用户新上传文件或查数据概览（文件模式）
- data_cleaner:  数据加载完成但未清洗
- eda:           需了解分布/统计/相关性
- visualization: 需图表
- ml_agent:      需建模/预测
- reporter:      汇总结果生成报告
- FINISH:        所有分析完成

回复 JSON: {"next": "agent_name", "reason": "简短理由"}
"""


class SupervisorAgent(BaseAgent):
    """
    Supervisor —— 不执行代码，只做路由决策。
    """

    name = "supervisor"

    @property
    def system_prompt(self) -> str:
        return SUPERVISOR_SYSTEM_PROMPT

    def build_user_prompt(self, state: DataAnalysisState) -> str:
        """根据 state 构建 supervisor 的用户消息。"""
        parts = []

        parts.append(f"## 用户问题\n{state.get('user_query', '未指定')}")

        parts.append(f"\n## 分析计划\n")
        plan = state.get("analysis_plan", [])
        completed = state.get("completed_steps", [])
        for i, step in enumerate(plan):
            status = "✅" if step in completed else "⬜"
            parts.append(f"- {status} {step}")

        parts.append(f"\n## 数据状态")
        parts.append(f"- 文件: {state.get('file_path', '未加载')}")
        parts.append(f"- 行数: {state.get('row_count', 'N/A')}")
        parts.append(f"- 列数: {state.get('column_count', 'N/A')}")

        parts.append(f"\n## 代码执行历史（最近 3 条）")
        history = state.get("code_history", [])
        for h in history[-3:]:
            parts.append(f"- [{h['agent']}] {'✅' if h['success'] else '❌'}: {h['output'][:200]}")

        if state.get("error"):
            parts.append(f"\n## 最近错误\n{state['error']}")

        parts.append(f"\n## 循环计数: {state.get('loop_count', 0)} / {config.MAX_WORKFLOW_LOOPS}")

        parts.append("\n请决定下一步路由（JSON 格式）。")
        return "\n".join(parts)

    def run(self, state: DataAnalysisState) -> dict:
        """Supervisor 特殊流程：不执行代码，直接返回路由决策。"""
        response = self.call_llm(state)

        # 解析 JSON 决策
        decision = self._parse_decision(response)

        return {
            "next_agent": decision["next"],
            "messages": [AIMessage(content=f"[Supervisor] 路由到 {decision['next']}: {decision['reason']}")],
        }

    @staticmethod
    def _parse_decision(text: str) -> dict:
        """从 LLM 响应中提取路由决策 JSON。"""
        # 尝试直接解析 JSON
        json_pattern = r"\{[^{}]*\"next\"[^{}]*\}"
        match = re.search(json_pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # 回退：关键词匹配
        for agent_name in list(ROUTING_DESCRIPTIONS.keys()):
            if agent_name.lower() in text.lower():
                return {"next": agent_name, "reason": f"关键词匹配到 {agent_name}"}

        return {"next": "FINISH", "reason": "无法解析决策，默认结束"}


