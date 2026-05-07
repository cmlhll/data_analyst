"""
DataLoader Agent —— 加载数据文件并生成数据摘要。
"""

from .base import BaseAgent
from state import DataAnalysisState


LOADER_SYSTEM_PROMPT = """你是一个数据加载专家。你的任务是：
1. 使用 pandas 加载指定的数据文件
2. 检查数据类型、缺失值、重复行
3. 生成数据摘要报告

输出格式：
- 先用自然语言描述数据概况
- 然后用 ```python ... ``` 代码块包含完整的分析代码

代码要求：
- 变量 `df` 已经被加载为 pandas DataFrame
- 使用 print() 输出关键信息
- 输出应包括：shape, dtypes, missing counts, duplicate count, head(10), describe()
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
        # 简单正则提取
        import re
        output = result.get("last_output", "")
        shape_match = re.search(r"(\d+)\s*[行row]+\s*[×xX]\s*(\d+)\s*[列col]+", output, re.IGNORECASE)
        if shape_match:
            result["row_count"] = int(shape_match.group(1))
            result["column_count"] = int(shape_match.group(2))

        return result
