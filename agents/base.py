"""
Agent 基类 —— 通用 LLM 调用、代码生成、结果解析模式。
包含路径遍历防护和统一错误处理。
"""
import json
import logging
import os
import re
import time as _time
import traceback as _traceback
from abc import ABC, abstractmethod
from typing import Any, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

import config
from state import DataAnalysisState
from tools.code_executor import CodeExecutor
from self_inspect import record_issue

logger = logging.getLogger(__name__)

# 项目根目录，用于路径遍历校验
_PROJECT_ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))


def _validate_path_safety(file_path: str) -> str:
    """
    校验文件路径是否在项目根目录内，防止路径遍历攻击。
    返回安全的绝对路径，如果越权则抛出 PermissionError。
    """
    real = os.path.realpath(file_path)
    if not real.startswith(_PROJECT_ROOT + os.sep) and real != _PROJECT_ROOT:
        raise PermissionError(
            f"路径遍历拒绝: {real} 不在项目根目录 {_PROJECT_ROOT} 内"
        )
    return real


class BaseAgent(ABC):
    """
    每个 Agent 继承此类，实现：
    - system_prompt: 系统提示词
    - build_user_prompt(state): 根据 state 构建用户消息
    - parse_result(text): 解析 LLM 返回
    """

    name: str = "base"

    def __init__(self, llm: Optional[ChatOpenAI] = None) -> None:
        self.llm = llm or self._default_llm()
        self.executor = CodeExecutor()

    @staticmethod
    def _default_llm() -> ChatOpenAI:
        kwargs: dict[str, Any] = {
            "model": config.LLM_MODEL,
            "temperature": config.LLM_TEMPERATURE,
            "max_tokens": config.LLM_CODE_MAX_TOKENS,
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
            # 作为最后手段，返回整个响应
            return [text.strip()]
        return [m.strip() for m in matches]

    def run(self, state: DataAnalysisState) -> dict[str, Any]:
        """
        标准执行流程：
        1. LLM 生成分析代码
        2. 代码沙箱执行
        3. 将结果写回 state
        4. 记录执行时序和检测问题（自检系统）

        统一 try/except 包装，异常时返回结构化错误 state。
        """
        try:
            logger.info("Agent [%s] 开始执行", self.name)
            start_time = _time.monotonic()
            llm_response = self.call_llm(state)
            code_blocks = self.extract_code_blocks(llm_response)

            # 构建 preamble（共享的导入和数据加载）
            preamble = self._build_preamble(state)

            all_outputs: list[dict] = []
            all_figures: list[str] = []
            success = True

            for i, code in enumerate(code_blocks):
                result = self.executor.execute(code, preamble=preamble)
                all_outputs.append(result)
                all_figures.extend(result.get("figure_paths", []))
                if not result["success"]:
                    success = False
                # 只执行第一个代码块就够了（通常 Agent 只生成一个块）
                break

            elapsed_ms = (_time.monotonic() - start_time) * 1000.0

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
            code_used = code_blocks[0] if code_blocks else ""
            history_entry: dict[str, Any] = {
                "agent": self.name,
                "code": code_used,
                "output": combined_output,
                "success": success,
                "duration_ms": elapsed_ms,
            }

            updated_history = state.get("code_history", []) + [history_entry]
            updated_figures = state.get("figure_paths", []) + all_figures

            # ── 自检：检测问题 ────────────────────────────
            issues = self._detect_issues(
                state, code_used, success, combined_output, elapsed_ms,
            )

            logger.info(
                "Agent [%s] 执行完成, success=%s, duration=%.0fms, issues=%d",
                self.name, success, elapsed_ms, len(issues),
            )
            return {
                "last_code": code_used,
                "last_output": combined_output,
                "code_history": updated_history,
                "figure_paths": updated_figures,
                "error": None if success else f"{self.name} 执行出错",
                "inspection_log": issues,
            }

        except Exception:
            error_msg = f"{self.name} 异常"
            logger.exception("Agent [%s] 异常", self.name)
            # 记录异常到自检系统
            err_issue = record_issue(
                state,
                category="CODE_FAILURE",
                severity="HIGH",
                detail=_traceback.format_exc(),
                agent_name=self.name,
            )
            return {
                "last_code": "",
                "last_output": _traceback.format_exc(),
                "code_history": state.get("code_history", []) + [
                    {"agent": self.name, "code": "", "output": error_msg, "success": False}
                ],
                "figure_paths": state.get("figure_paths", []),
                "error": error_msg,
                "inspection_log": [err_issue],
            }

    def _build_preamble(self, state: DataAnalysisState) -> str:
        """构建代码前置 —— 导入常用库并加载数据。包含路径安全校验。

        数据集模式下跳过硬编码的文件加载（由 DataUnderstander 处理）。
        """
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
        mode = state.get("mode", "file")

        # 数据集模式：data_understander 已经加载了数据到 pickle
        # 从工作副本加载 df（如果存在）
        if mode == "dataset":
            sandbox_dir = config.SANDBOX_DIR
            preamble += f"""
import os as _os

_working = _os.path.join(r"{sandbox_dir}", '_working_data.pkl')
if _os.path.exists(_working):
    try:
        df = pd.read_pickle(_working)
        print(f"✅ 从工作副本加载: {{df.shape[0]}} 行 × {{df.shape[1]}} 列")
    except Exception:
        _os.remove(_working)
        raise
else:
    df = pd.DataFrame()
    print("⚠️ 工作副本不存在，使用空 DataFrame")
"""
            return preamble.strip()

        # 文件模式：加载数据：优先从工作副本 (pickle)，fallback 到原始文件
        raw_path = state.get("file_path")
        if raw_path:
            sandbox_dir = config.SANDBOX_DIR
            safe_path = _validate_path_safety(raw_path)
            preamble += f"""
import os as _os
import sys
sys.path.insert(0, r"{sandbox_dir}")

_working = _os.path.join(r"{sandbox_dir}", '_working_data.pkl')
if _os.path.exists(_working):
    try:
        df = pd.read_pickle(_working)
        print(f"✅ 从工作副本加载: {{df.shape[0]}} 行 × {{df.shape[1]}} 列")
    except Exception:
        _os.remove(_working)  # 损坏的 pickle，回退
        raise
else:
    # 首次加载：根据文件扩展名选择读取方式
    _path = r"{safe_path}"
    _ext = _os.path.splitext(_path)[1].lower()
    if _ext in ('.xlsx', '.xls'):
        df = pd.read_excel(_path)
    elif _ext == '.json':
        df = pd.read_json(_path)
    elif _ext == '.parquet':
        df = pd.read_parquet(_path)
    elif _ext == '.tsv':
        df = pd.read_csv(_path, sep='\\t')
    else:
        df = pd.read_csv(_path)
    print(f"✅ 首次加载原始数据: {{df.shape[0]}} 行 × {{df.shape[1]}} 列")
    # 建立工作副本
    df.to_pickle(_working)
"""
        return preamble.strip()

    def _detect_issues(
        self,
        state: DataAnalysisState,
        code: str,
        success: bool,
        output: str,
        duration_ms: float,
    ) -> list[dict]:
        """
        分析执行结果，检测问题并记录到自检系统。

        检测策略：
        - 代码执行失败 → CODE_FAILURE (HIGH)
        - 执行时间超过阈值 → EXECUTION_SLOW (MEDIUM / HIGH)
        - 输出中出现内存相关错误 → MEMORY_HIGH (HIGH)
        - 输出中出现意外空值 → UNEXPECTED_NULL (LOW)
        - 数据加载阶段的错误 → DATA_LOAD_ERROR (HIGH)
        """
        issues: list[dict] = []

        # 1. 代码执行失败
        if not success:
            issues.append(record_issue(
                state,
                category="CODE_FAILURE",
                severity="HIGH",
                detail=f"Agent [{self.name}] 代码执行失败，输出前200字符: {output[:200]}",
                agent_name=self.name,
                duration_ms=duration_ms,
            ))

        # 2. 执行速度慢
        if duration_ms > config.SLOW_EXECUTION_THRESHOLD_MS:
            severity = "HIGH" if duration_ms > config.SLOW_EXECUTION_THRESHOLD_MS * 2 else "MEDIUM"
            issues.append(record_issue(
                state,
                category="EXECUTION_SLOW",
                severity=severity,
                detail=f"Agent [{self.name}] 执行耗时 {duration_ms:.0f}ms，"
                       f"超过阈值 {config.SLOW_EXECUTION_THRESHOLD_MS}ms",
                agent_name=self.name,
                duration_ms=duration_ms,
            ))

        # 3. 内存异常
        mem_keywords = ["memory", "Memory", "MemoryError", "OutOfMemory"]
        if any(kw in output for kw in mem_keywords):
            issues.append(record_issue(
                state,
                category="MEMORY_HIGH",
                severity="HIGH",
                detail=f"Agent [{self.name}] 输出中包含内存异常关键词",
                agent_name=self.name,
                duration_ms=duration_ms,
            ))

        # 4. 数据加载异常（只对 data_loader agent 检查）
        if self.name == "data_loader" and not success:
            issues.append(record_issue(
                state,
                category="DATA_LOAD_ERROR",
                severity="HIGH",
                detail=f"数据加载失败: {output[:300]}",
                agent_name=self.name,
                duration_ms=duration_ms,
            ))

        # 5. 意外的空值（只对 data_cleaner / eda 检查）
        if self.name in ("data_cleaner", "eda") and success:
            null_keywords = ["NaN", "nan", "None", "null", "missing"]
            null_count = sum(1 for kw in null_keywords if kw in output)
            if null_count >= 2:
                issues.append(record_issue(
                    state,
                    category="UNEXPECTED_NULL",
                    severity="LOW",
                    detail=f"Agent [{self.name}] 输出中发现 {null_count} 类空值关键词",
                    agent_name=self.name,
                    duration_ms=duration_ms,
                ))

        return issues
