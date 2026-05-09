# data_analyst 离线评测

这个目录用于评估用户上传文件 + 自然语言问题的数据分析 Agent。

## 评测目标

覆盖以下能力：

- 文件读取与字段理解
- 数据质量检查：缺失值、重复行
- EDA：趋势、异常、分组对比
- 可视化：用户要求趋势/图表时是否生成图表
- ML：用户要求建模时是否调用建模流程并给出指标
- 报告质量：最终报告是否覆盖关键事实
- 执行可靠性：代码历史是否成功执行

## 快速运行

默认 mock 模式，不调用 LLM，适合 CI 验证评测链路：

```bash
python -m eval.run_eval
```

运行真实 LangGraph Agent：

```bash
python -m eval.run_eval --mode agent
```

输出：

```text
eval/generated_data/      # 自动生成的 CSV 与 cases.json
eval/results/             # 评测明细与 Markdown 报告
```

## 评测集

当前自动生成两个代表性数据集：

1. `sales_anomaly.csv`
   - 电商 GMV 日粒度数据
   - 注入直播渠道异常下跌
   - 用于评估趋势、异常、渠道拆解、可视化

2. `customer_churn.csv`
   - 客户流失分类数据
   - 注入 nps 缺失值和重复行
   - 用于评估数据清洗、EDA、分类建模、模型指标

## 评分逻辑

`eval/scorers.py` 当前采用规则评分：

- keyword coverage：报告/执行输出是否覆盖标准关键词
- agent coverage：是否执行必要 Agent
- execution success：代码历史是否成功
- visualization：需要图表时是否生成 figure
- ml metrics：需要建模时是否出现模型指标

后续可以扩展：

- 数值断言抽取与精确校验
- LLM-as-Judge 评估洞察质量
- 安全与无证据归因检测
- 执行轨迹回放与回归测试

## 设计原则

评测模块不侵入主链路。真实评测只通过 `graph.run_analysis` 接入，mock 模式用于本地和 CI 稳定运行。
