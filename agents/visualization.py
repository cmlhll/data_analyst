"""
Visualization Agent —— 数据可视化：柱状图、散点图、热力图、箱线图等。
"""

import os
import config
from .base import BaseAgent
from state import DataAnalysisState


VIZ_SYSTEM_PROMPT = """你是数据可视化专家。输出 ```python ... ``` 代码块，用 print() 输出保存路径。

要求：
- 变量 `df` 已加载
- 用 matplotlib/seaborn，MPLBACKEND=Agg
- plt.savefig() 保存到当前目录，文件名含描述性名称
- 添加标题、轴标签、图例
- 大数据集采样显示
- 不要 plt.show()
"""


class VisualizationAgent(BaseAgent):
    """数据可视化：生成分析图表。"""

    name = "visualization"

    @property
    def system_prompt(self) -> str:
        return VIZ_SYSTEM_PROMPT

    def build_user_prompt(self, state: DataAnalysisState) -> str:
        parts = []
        parts.append(f"## 数据概况")
        parts.append(f"- 列名: {state.get('column_names', [])}")
        parts.append(f"- 数据类型: {state.get('dtypes', {})}")

        if state.get("last_output"):
            parts.append(f"\n## 最近的 EDA 结果\n```\n{state['last_output'][:500]}\n```")

        parts.append(f"\n## 用户问题\n{state.get('user_query', '')}")
        parts.append(f"\n## 已生成的图表\n{state.get('figure_paths', [])}")

        parts.append("\n请根据数据特点选择合适的可视化并执行。")
        return "\n".join(parts)
