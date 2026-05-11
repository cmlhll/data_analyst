"""
EDA Agent —— 探索性数据分析：统计描述、分布、相关性。
"""

from .base import BaseAgent
from state import DataAnalysisState


EDA_SYSTEM_PROMPT = """你是 EDA 专家。输出 ```python ... ``` 代码块，用 print() 输出结果。

要求：
- 变量 `df` 已加载
- 输出：数值列描述统计、分类列频次、相关性矩阵、Top 强相关性对
- **明确写出异常日期和数值**（如 GMV 单日大跌的具体日期）
- 大数据集使用采样
"""


class EDAAgent(BaseAgent):
    """探索性数据分析：统计、分布、相关性。"""

    name = "eda"

    @property
    def system_prompt(self) -> str:
        return EDA_SYSTEM_PROMPT

    def build_user_prompt(self, state: DataAnalysisState) -> str:
        parts = []
        parts.append(f"## 数据概况")
        parts.append(f"- 行数: {state.get('row_count', 'N/A')}")
        parts.append(f"- 列数: {state.get('column_count', 'N/A')}")
        parts.append(f"- 列名: {state.get('column_names', [])}")
        parts.append(f"- 数据类型: {state.get('dtypes', {})}")

        if state.get("last_output"):
            parts.append(f"\n## 上一步输出\n```\n{state['last_output'][:500]}\n```")

        parts.append(f"\n## 用户问题\n{state.get('user_query', '')}")
        parts.append("\n请执行探索性数据分析。")
        return "\n".join(parts)
