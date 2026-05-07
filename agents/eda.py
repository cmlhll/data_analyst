"""
EDA Agent —— 探索性数据分析：统计描述、分布、相关性。
"""

from .base import BaseAgent
from state import DataAnalysisState


EDA_SYSTEM_PROMPT = """你是一个探索性数据分析（EDA）专家。你的任务是：
1. 计算数值列的描述统计（均值、中位数、标准差、偏度、峰度）
2. 分析分类列的频次分布（value_counts）
3. 计算数值列之间的相关性矩阵
4. 识别前 N 个最强的相关性对
5. 提供数据洞察（异常分布、强相关、类别不平衡等）

输出格式：
- 先用自然语言描述关键发现
- 然后用 ```python ... ``` 代码块包含完整的分析代码

代码要求：
- 变量 `df` 已被加载
- 使用 print() 输出统计结果
- 对大数据集使用采样或限制输出行数
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
            parts.append(f"\n## 上一步输出\n```\n{state['last_output'][:2000]}\n```")

        parts.append(f"\n## 用户问题\n{state.get('user_query', '')}")
        parts.append("\n请执行探索性数据分析。")
        return "\n".join(parts)
