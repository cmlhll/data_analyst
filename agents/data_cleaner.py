"""
DataCleaner Agent —— 数据清洗：缺失值、异常值、类型转换、去重。
"""

from .base import BaseAgent
from state import DataAnalysisState


CLEANER_SYSTEM_PROMPT = """你是一个数据清洗专家。你的任务是：
1. 识别并处理缺失值（删除 / 填充均值/中位数/众数 / 前向填充）
2. 检测并处理异常值（IQR / Z-score > 3）
3. 修正数据类型（object → datetime, object → numeric 等）
4. 删除重复行
5. 标准化列名（去除空格、统一大小写）

输出格式：
- 先用自然语言描述清洗策略
- 然后用 ```python ... ``` 代码块包含完整的清洗代码

代码要求：
- 变量 `df` 已被加载，清洗后的数据写回 `df`
- 使用 print() 报告每一步清洗前后的变化
- 每一步清洗都要打印：处理了什么、影响多少行
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
            parts.append(f"\n## 数据摘要\n```\n{state['data_info'][:3000]}\n```")

        if state.get("last_output"):
            parts.append(f"\n## 上一步输出\n```\n{state['last_output'][:2000]}\n```")

        parts.append(f"\n## 用户问题\n{state.get('user_query', '')}")
        parts.append("\n请制定清洗策略并执行。")
        return "\n".join(parts)
