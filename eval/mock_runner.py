"""Deterministic mock states for quick eval pipeline checks."""
from __future__ import annotations


def run_mock(case: dict) -> dict:
    q = case.get('query', '')
    expected = case.get('expected', {})
    code_history = [
        {'agent': 'data_loader', 'code': 'pd.read_csv(file_path)', 'output': 'shape, dtypes, missing counts, duplicate count', 'success': True},
        {'agent': 'eda', 'code': 'df.describe(); groupby analysis', 'output': 'EDA summary with key metrics', 'success': True},
    ]
    figures = []
    report = f"# 分析报告\n\n用户问题：{q}\n\n"
    if case.get('dataset_id') == 'sales_anomaly':
        code_history.append({'agent': 'visualization', 'code': 'plot trend', 'output': 'generated trend chart', 'success': True})
        figures.append('mock_sales_trend.png')
        report += f"GMV 在4月存在异常波动，异常日期是 {expected.get('anomaly_date')}。主要渠道是 {expected.get('top_channel')}。建议继续按渠道和日期下钻，当前只能说明数据事实和可能原因，不能直接归因到个人。"
    elif case.get('dataset_id') == 'customer_churn':
        code_history.insert(1, {'agent': 'data_cleaner', 'code': 'drop_duplicates; impute nps', 'output': '发现nps缺失和重复行', 'success': True})
        code_history.append({'agent': 'ml_agent', 'code': 'train_test_split; RandomForestClassifier', 'output': '模型 accuracy=0.82, f1=0.61, key features: usage_days_30d, nps', 'success': True})
        report += "发现 nps 存在缺失，数据存在重复行。目标变量 churned 可用于流失分类模型。模型评估包含 accuracy 和 f1，关键特征包括 usage_days_30d、nps、support_tickets_90d。"
    else:
        report += '完成基础分析。'
    return {'report': report, 'code_history': code_history, 'figure_paths': figures, 'error': None}
