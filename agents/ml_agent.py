"""
ML Agent —— 机器学习建模：特征工程、模型训练、评估。
"""

from .base import BaseAgent
from state import DataAnalysisState


ML_SYSTEM_PROMPT = """你是 ML 专家。输出 ```python ... ``` 代码块，用 print() 输出模型指标。

要求：
- 变量 `df` 已加载
- 特征工程（编码、缩放）→ train/test split → 模型训练 → 评估
- 分类: accuracy, precision, recall, f1, confusion_matrix
- 回归: mse, mae, r2
- 特征重要性用 matplotlib 保存
"""


class MLAgent(BaseAgent):
    """机器学习建模：特征工程、训练、评估。"""

    name = "ml_agent"

    @property
    def system_prompt(self) -> str:
        return ML_SYSTEM_PROMPT

    def build_user_prompt(self, state: DataAnalysisState) -> str:
        parts = []
        parts.append(f"## 数据概况")
        parts.append(f"- 列名: {state.get('column_names', [])}")
        parts.append(f"- 数据类型: {state.get('dtypes', {})}")

        if state.get("last_output"):
            parts.append(f"\n## EDA 结果\n```\n{state['last_output'][:500]}\n```")

        parts.append(f"\n## 用户问题\n{state.get('user_query', '')}")
        parts.append("\n请设计并执行机器学习建模流程。")
        return "\n".join(parts)
