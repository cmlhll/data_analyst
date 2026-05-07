"""
Agent 基类 —— 通用 LLM 调用、代码生成、结果解析模式。
"""

import json
import re
from typing import Optional
from abc import ABC, abstractmethod

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

import config
from state import DataAnalysisState
from tools.code_executor import CodeExecutor


class BaseAgent(ABC):
    """
    每个 Agent 继承此类，实现：
    - system_prompt: 系统提示词
    - build_user_prompt(state): 根据 state 构建用户消息
    - parse_result(text): 解析 LLM 返回
    """

    name: str = "base"

    def __init__(self, llm: Optional[ChatOpenAI] = None):
        self.llm = llm or self._default_llm()
        self.executor = CodeExecutor()

    @staticmethod
    def _default_llm() -> ChatOpenAI:
        kwargs = {
            "model": config.LLM_MODEL,
            "temperature": config.LLM_TEMPERATURE,
            "max_tokens": config.LLM_MAX_TOKENS,
        }
        if config.LLM_API_KEY:
            kwargs["api_key"] = config.LLM_API_KEY
        if config.LLM_BASE_URL:
            kwargs["base_url"] = config.LLM_BASE_URL
        return ChatOpenAI(**kwargs)

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Agent 的系统提示词。"""
        ...

    @abstractmethod
    def build_user_prompt(self, state: DataAnalysisState) -> str:
        """根据当前 state 构建用户消息。"""
        ...

    def call_llm(self, state: DataAnalysisState) -> str:
        """调用 LLM，返回生成文本。"""
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=self.build_user_prompt(state)),
        ]
        response = self.llm.invoke(messages)
        return response.content

    @staticmethod
    def extract_code_blocks(text: str) -> list[str]:
        """从 LLM 响应中提取 ```python ... ``` 代码块。"""
        pattern = r"```python\s*\n(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)
        if not matches:
            # 尝试不带语言标识的 code block
            pattern = r"```\s*\n(.*?)```"
            matches = re.findall(pattern, text, re.DOTALL)
        if not matches:
            # 尝试只匹配缩进的代码（无 markdown 标记）
            # 作为最后手段，返回整个响应
            return [text.strip()]
        return [m.strip() for m in matches]

    def run(self, state: DataAnalysisState) -> dict:
        """
        标准执行流程：
        1. LLM 生成分析代码
        2. 代码沙箱执行
        3. 将结果写回 state
        """
        llm_response = self.call_llm(state)
        code_blocks = self.extract_code_blocks(llm_response)

        # 构建 preamble（共享的导入和数据加载）
        preamble = self._build_preamble(state)

        all_outputs = []
        all_figures = []
        success = True

        for i, code in enumerate(code_blocks):
            result = self.executor.execute(code, preamble=preamble)
            all_outputs.append(result)
            all_figures.extend(result.get("figure_paths", []))
            if not result["success"]:
                success = False

            # 只执行第一个代码块就够了（通常 Agent 只生成一个块）
            break

        # 聚合输出
        combined_output = ""
        for r in all_outputs:
            if r["stdout"]:
                combined_output += r["stdout"] + "\n"
            if r["stderr"]:
                combined_output += r["stderr"] + "\n"
            if r["error"]:
                combined_output += f"[ERROR] {r['error']}\n"

        # 更新 code_history
        history_entry = {
            "agent": self.name,
            "code": code_blocks[0] if code_blocks else "",
            "output": combined_output,
            "success": success,
        }

        updated_history = state.get("code_history", []) + [history_entry]
        updated_figures = state.get("figure_paths", []) + all_figures

        return {
            "last_code": code_blocks[0] if code_blocks else "",
            "last_output": combined_output,
            "code_history": updated_history,
            "figure_paths": updated_figures,
            "error": None if success else f"{self.name} 执行出错",
        }

    def _build_preamble(self, state: DataAnalysisState) -> str:
        """构建代码前置 —— 导入常用库并加载数据。"""
        preamble = """
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import json
import os
from datetime import datetime

# 设置中文显示（如果可用）
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
sns.set_style("whitegrid")
"""
        # 如果有数据文件路径，加载数据
        if state.get("file_path"):
            preamble += f"""
# 加载数据
import sys
sys.path.insert(0, r"{config.SANDBOX_DIR}")
df = pd.read_csv(r"{state['file_path']}")
print(f"✅ 数据加载成功: {{df.shape[0]}} 行 × {{df.shape[1]}} 列")
"""
        return preamble.strip()
