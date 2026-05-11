"""
Reporter Agent —— 汇总分析结果，生成 Markdown 报告。
"""

from typing import Any, Optional

from .base import BaseAgent
from state import DataAnalysisState


REPORTER_SYSTEM_PROMPT = """你是数据分析报告撰写专家。根据所有 Agent 的分析结果生成一份结构化 Markdown 报告。

报告结构：
1. **概述** — 分析目标、数据概况
2. **数据质量** — 缺失值、异常值、清洗过程
3. **探索性分析** — 关键统计发现、分布特点、相关性
4. **可视化** — 生成的图表清单及解读
5. **建模结果** — 模型性能、特征重要性（如有）
6. **结论与建议** — 总结发现，给出可行动建议

输出 Markdown 文本即可，不要代码块。保持简洁，突出关键数字和洞察。
"""


class ReporterAgent(BaseAgent):
    """汇总分析结果，生成 Markdown 报告。"""

    name = "reporter"

    def __init__(self, llm: Optional[ChatOpenAI] = None) -> None:
        # Reporter 需要更大的 output token 来生成完整报告
        if llm is None:
            import config
            kwargs: dict[str, Any] = {
                "model": config.LLM_MODEL,
                "temperature": config.LLM_TEMPERATURE,
                "max_tokens": config.LLM_REPORT_MAX_TOKENS,
            }
            if config.LLM_API_KEY:
                kwargs["api_key"] = config.LLM_API_KEY
            if config.LLM_BASE_URL:
                kwargs["base_url"] = config.LLM_BASE_URL
            llm = ChatOpenAI(**kwargs)
        super().__init__(llm)

    @property
    def system_prompt(self) -> str:
        return REPORTER_SYSTEM_PROMPT

    def build_user_prompt(self, state: DataAnalysisState) -> str:
        parts = []
        parts.append(f"## 用户问题\n{state.get('user_query', '未指定')}")

        parts.append(f"\n## 数据概况")
        parts.append(f"- 文件: {state.get('file_path', '')}")
        parts.append(f"- 行数: {state.get('row_count', 'N/A')}")
        parts.append(f"- 列数: {state.get('column_count', 'N/A')}")
        parts.append(f"- 列名: {state.get('column_names', [])}")

        parts.append(f"\n## 分析计划")
        for i, step in enumerate(state.get("analysis_plan", [])):
            done = "✅" if step in state.get("completed_steps", []) else "⬜"
            parts.append(f"- {done} {step}")

        # 只取每个 Agent 关键输出的最后 500 字符
        parts.append(f"\n## 各 Agent 关键输出")
        for h in state.get("code_history", []):
            status = "✅" if h["success"] else "❌"
            output_snippet = h.get("output", "")[:500]
            parts.append(f"\n### [{h['agent']}] {status}\n```\n{output_snippet}\n```")

        parts.append(f"\n## 已生成的图表\n{state.get('figure_paths', [])}")

        if state.get("error"):
            parts.append(f"\n## 错误\n{state['error']}")

        parts.append("\n请基于以上信息生成最终分析报告（Markdown）。")
        return "\n".join(parts)

    def run(self, state: DataAnalysisState) -> dict:
        """
        Reporter 特殊流程：不执行代码，直接生成 Markdown 报告。
        """
        response = self.call_llm(state)
        return {
            "report": response,
            "last_output": response,
            "messages": [],
        }
