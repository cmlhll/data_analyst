"""
ML Agent —— 机器学习建模：特征工程、模型训练、评估。
"""

from .base import BaseAgent
from state import DataAnalysisState


ML_SYSTEM_PROMPT = """你是一个机器学习专家。你的任务是：
1. 识别目标变量（用户指定或自动推断）
2. 特征工程（编码分类变量、缩放数值特征、处理缺失值）
3. 数据划分（train/test split）
4. 选择合适的模型：
   - 分类: LogisticRegression, RandomForestClassifier, GradientBoostingClassifier
   - 回归: LinearRegression, RandomForestRegressor, GradientBoostingRegressor
   - 聚类: KMeans, DBSCAN
5. 训练模型
6. 评估（分类: accuracy, precision, recall, f1, confusion_matrix；回归: mse, mae, r2）
7. 特征重要性分析

输出格式：
- 先用自然语言描述建模策略和结果解读
- 然后用 ```python ... ``` 代码块包含完整的建模代码

代码要求：
- 变量 `df` 已被加载
- 使用 sklearn 库
- 使用 print() 输出模型评估指标
- 对于特征重要性，保存为 matplotlib 图表
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
            parts.append(f"\n## EDA 结果\n```\n{state['last_output'][:2000]}\n```")

        parts.append(f"\n## 用户问题\n{state.get('user_query', '')}")
        parts.append("\n请设计并执行机器学习建模流程。")
        return "\n".join(parts)
