"""
DataCleaner Agent —— 数据清洗：缺失值、异常值、类型转换、去重。
"""

from .base import BaseAgent
from state import DataAnalysisState


CLEANER_SYSTEM_PROMPT = """你是数据清洗专家。输出 ```python ... ``` 代码块，用 print() 报告每一步变化。

要求：
- 变量 `df` 已加载，清洗后写回 `df`
- 处理：缺失值填充/删除、异常值检测(IQR/Z-score)、类型修正、去重、列名标准化
- 每步用 print() 报告：处理了什么、影响多少行
"""


class DataCleanerAgent(BaseAgent):
    """清洗数据：缺失值、异常值、类型修正、去重。"""

    name = "data_cleaner"

    @property
    def system_prompt(self) -> str:
        return CLEANER_SYSTEM_PROMPT

    def build_user_prompt(self, state: DataAnalysisState) -> str:
        parts = []
        parts.append(f"## 数据概况")
        parts.append(f"- 文件: {state.get('file_path', '')}")
        parts.append(f"- 行数: {state.get('row_count', 'N/A')}")
        parts.append(f"- 列数: {state.get('column_count', 'N/A')}")
        parts.append(f"- 列名: {state.get('column_names', [])}")
        parts.append(f"- 数据类型: {state.get('dtypes', {})}")

        if state.get("data_info"):
            parts.append(f"\n## 数据摘要\n```\n{state['data_info'][:1000]}\n```")

        if state.get("last_output"):
            parts.append(f"\n## 上一步输出\n```\n{state['last_output'][:500]}\n```")

        parts.append(f"\n## 用户问题\n{state.get('user_query', '')}")
        parts.append("\n请制定清洗策略并执行。")
        return "\n".join(parts)
