"""Small deterministic eval data generator."""
from pathlib import Path
import json
import numpy as np
import pandas as pd


def gen_sales(out: Path):
    rng = np.random.default_rng(42)
    rows = []
    for d in pd.date_range('2026-04-01', '2026-04-30'):
        for channel in ['自然流量', '直播', '搜索广告', '私域']:
            base = {'自然流量': 100, '直播': 140, '搜索广告': 90, '私域': 70}[channel]
            if str(d.date()) == '2026-04-18' and channel == '直播':
                base *= 0.35
            orders = int(rng.poisson(base))
            gmv = round(orders * rng.normal(520, 30), 2)
            rows.append({'date': str(d.date()), 'channel': channel, 'orders': orders, 'gmv': gmv})
    df = pd.DataFrame(rows)
    path = out / 'sales_anomaly.csv'
    df.to_csv(path, index=False)
    daily = df.groupby('date', as_index=False).gmv.sum()
    daily['dod'] = daily.gmv.pct_change()
    an = daily.iloc[1:].assign(abs_dod=lambda x: x.dod.abs()).sort_values('abs_dod', ascending=False).iloc[0]
    top_channel = df.groupby('channel').gmv.sum().sort_values(ascending=False).index[0]
    return {
        'dataset_id': 'sales_anomaly',
        'file_path': str(path),
        'query': '分析4月销售表现，指出GMV趋势、异常日期和主要渠道。',
        'expected_keywords': ['GMV', '异常', str(an.date), str(top_channel)],
        'required_agents': ['data_loader', 'eda', 'visualization', 'reporter'],
        'expected': {'anomaly_date': str(an.date), 'top_channel': str(top_channel)}
    }


def gen_churn(out: Path):
    rng = np.random.default_rng(7)
    n = 500
    usage = rng.integers(0, 31, n)
    tickets = rng.poisson(1.2, n)
    late = rng.poisson(.4, n)
    nps = np.clip(rng.normal(7, 2, n).round(), 0, 10)
    logit = -2 - .08 * usage + .45 * tickets + .7 * late - .22 * nps
    churned = rng.binomial(1, 1 / (1 + np.exp(-logit)))
    df = pd.DataFrame({'customer_id': [f'C{i:04d}' for i in range(n)], 'usage_days_30d': usage, 'support_tickets_90d': tickets, 'late_payments_12m': late, 'nps': nps, 'churned': churned})
    df.loc[rng.choice(df.index, 15, replace=False), 'nps'] = np.nan
    df = pd.concat([df, df.iloc[:5]], ignore_index=True)
    path = out / 'customer_churn.csv'
    df.to_csv(path, index=False)
    return {
        'dataset_id': 'customer_churn',
        'file_path': str(path),
        'query': '检查客户流失数据质量，训练流失分类模型，并说明关键特征和评估指标。',
        'expected_keywords': ['缺失', '重复', 'churned', '模型', '特征'],
        'required_agents': ['data_loader', 'data_cleaner', 'eda', 'ml_agent', 'reporter'],
        'expected': {'target': 'churned', 'missing_column': 'nps', 'duplicate_rows_min': 5}
    }


def generate_all(output_dir='eval/generated_data'):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    cases = [gen_sales(out), gen_churn(out)]
    with (out / 'cases.json').open('w', encoding='utf-8') as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)
    return cases


if __name__ == '__main__':
    print(json.dumps(generate_all(), ensure_ascii=False, indent=2))
