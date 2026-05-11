"""
DataLoader Agent —— 加载数据文件并生成数据摘要。
"""

import re

from .base import BaseAgent
from state import DataAnalysisState


LOADER_SYSTEM_PROMPT = """你是数据加载专家。输出 ```python ... ``` 代码块，用 print() 输出结果。

要求：
- 变量 `df` 已加载为 pandas DataFrame
- 输出：shape, dtypes, missing counts, duplicate count, head(10), describe()
"""


class DataLoaderAgent(BaseAgent):
    """加载数据并生成初始数据摘要。"""

    name = "data_loader"

    @property
    def system_prompt(self) -> str:
        return LOADER_SYSTEM_PROMPT

    def build_user_prompt(self, state: DataAnalysisState) -> str:
        parts = []
        parts.append(f"文件路径: {state.get('file_path', '未指定')}")
        parts.append(f"用户问题: {state.get('user_query', '')}")
        parts.append("\n请检查数据质量并生成摘要。")
        return "\n".join(parts)

    def run(self, state: DataAnalysisState) -> dict:
        result = super().run(state)

        # 从输出中解析 rows/cols
        output = result.get("last_output", "")
        shape_match = re.search(r"(\d+)\s*[行row]+\s*[×xX]\s*(\d+)\s*[列col]+", output, re.IGNORECASE)
        if shape_match:
            result["row_count"] = int(shape_match.group(1))
            result["column_count"] = int(shape_match.group(2))

        return result
