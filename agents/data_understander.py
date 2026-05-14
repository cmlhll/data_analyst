"""
DataUnderstander Agent —— 理解数据集元数据，根据用户问题决定加载哪些数据。

在数据集模式下，此 Agent 最先运行。读取 metadata.md 和用户问题，
理解需要用到哪些表和字段，生成 Python 代码加载数据到 df。
"""
import re
import os
from typing import Any, Optional

from .base import BaseAgent
from state import DataAnalysisState


UNDERSTANDER_SYSTEM_PROMPT = """你是数据理解专家。你的任务是：

1. 仔细阅读数据集元数据(metadata.md)，理解每个表的结构、字段含义和外键关系
2. 分析用户的分析需求，确定需要用到哪些表和字段
3. 生成 Python 代码，从数据文件加载必要的数据

代码生成要求：
- 变量 `df` 必须作为最终合并后的主 DataFrame
- 如果需要关联多个表，使用 pd.merge() 按外键关系连接
- 如果只需要单表，直接加载该文件
- 只加载用户问题需要的列（不要全表加载不需要的字段）
- 用 print() 输出加载后的数据概况（shape、列名、前5行）

元数据格式参考：
```
# 数据库名称
## table_name (表名描述)
- 描述：表的含义
- 字段：
  - field_name (PK/FK/type): 字段描述
```

输出格式：用 ```python ... ``` 包裹代码块。
"""


class DataUnderstanderAgent(BaseAgent):
    """数据集理解 Agent：分析元数据 + 用户问题 → 生成加载代码。"""

    name = "data_understander"

    @property
    def system_prompt(self) -> str:
        return UNDERSTANDER_SYSTEM_PROMPT

    def build_user_prompt(self, state: DataAnalysisState) -> str:
        parts = []

        # 数据集元数据
        metadata = state.get("metadata_content", "")
        if metadata:
            parts.append("## 数据集目录")
            parts.append(f"路径: {state.get('dataset_dir', '')}")
            parts.append(f"\n### 元数据 (metadata.md)\n```\n{metadata}\n```")

        # 可用数据文件
        data_tables = state.get("data_tables", {})
        if data_tables:
            parts.append("\n### 可用数据文件")
            for name, path in data_tables.items():
                parts.append(f"- {name}: {path}")

        # 用户问题
        parts.append(f"\n## 用户分析需求\n{state.get('user_query', '未指定')}")

        parts.append("\n请根据元数据分析和需求，生成 Python 代码加载必要数据到 `df`。")
        return "\n".join(parts)

    def run(self, state: DataAnalysisState) -> dict:
        """标准执行流程：LLM 生成代码 → 沙箱执行 → 返回结果。"""
        result = super().run(state)

        # 从输出中提取加载了哪些文件的信息
        output = result.get("last_output", "")
        shape_match = re.search(r"(\d+)\s*[行row]+\s*[×xX]\s*(\d+)\s*[列col]", output, re.IGNORECASE)
        if shape_match:
            result["row_count"] = int(shape_match.group(1))
            result["column_count"] = int(shape_match.group(2))
            result["data_info"] = output

        return result
