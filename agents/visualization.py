"""
Visualization Agent —— 数据可视化：柱状图、散点图、热力图、箱线图等。
"""

import os
import config
from .base import BaseAgent
from state import DataAnalysisState


VIZ_SYSTEM_PROMPT = """你是一个数据可视化专家。你的任务是创建高质量的数据图表。

可用图表类型：
- 柱状图 (bar): 分类对比
- 散点图 (scatter): 两个数值变量的关系
- 折线图 (line): 时间序列趋势
- 直方图 (hist): 数值分布
- 箱线图 (boxplot): 分布与异常值
- 热力图 (heatmap): 相关性矩阵
- 小提琴图 (violin): 分类分布
- 饼图 (pie): 占比
- 成对图 (pairplot): 多维关系（数据量大时采样）

输出格式：
- 先用自然语言描述图表选择理由
- 然后用 ```python ... ``` 代码块包含完整的绘图代码

代码要求：
- 变量 `df` 已被加载
- 使用 matplotlib/seaborn，设置 MPLBACKEND=Agg
- **必须**使用 plt.savefig() 保存图表到当前目录，文件名含描述性名称
- 图表要添加标题、轴标签、图例
- 选择合适的图表大小 figsize
- 对大数据集采样显示
- 保存后 print() 输出文件路径

重要：不要使用 plt.show()，使用 plt.savefig('figure_name.png', dpi=100, bbox_inches='tight')
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
            parts.append(f"\n## 最近的 EDA 结果\n```\n{state['last_output'][:2000]}\n```")

        parts.append(f"\n## 用户问题\n{state.get('user_query', '')}")
        parts.append(f"\n## 已生成的图表\n{state.get('figure_paths', [])}")

        parts.append("\n请根据数据特点选择合适的可视化并执行。")
        return "\n".join(parts)
