"""
代码沙箱执行器 —— 安全执行 LLM 生成的 Python 代码，捕获输出与异常。
"""

import os
import sys
import io
import traceback
import subprocess
import tempfile
import uuid
import re
from typing import Optional
from datetime import datetime

import config


class CodeExecutor:
    """
    在子进程中执行 Python 代码，提供：
    - 超时控制（config.CODE_TIMEOUT_SEC）
    - stdout/stderr 捕获
    - 输出行数截断
    - 安全的临时工作目录
    """

    def __init__(self):
        config.ensure_dirs()
        self.sandbox_dir = config.SANDBOX_DIR
        self.timeout = config.CODE_TIMEOUT_SEC
        self.max_lines = config.CODE_MAX_OUTPUT_LINES

    def execute(self, code: str, preamble: str = "") -> dict:
        """
        执行代码并返回结构化结果。

        Args:
            code: 要执行的 Python 代码
            preamble: 前置代码（如 import、数据加载），不会被截断输出

        Returns:
            {
                "success": bool,
                "stdout": str,
                "stderr": str,
                "error": str | None,
                "truncated": bool,
                "duration_ms": int,
                "figure_paths": list[str],   # 代码中 savefig 产生的文件
            }
        """
        full_code = self._build_full_code(preamble, code)
        script_path = self._write_temp_script(full_code)

        start = datetime.now()
        try:
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.sandbox_dir,
                env={**os.environ, "MPLBACKEND": "Agg"},
            )
            duration_ms = int((datetime.now() - start).total_seconds() * 1000)

            stdout = result.stdout
            stderr = result.stderr

            # 截断过长输出
            stdout_lines = stdout.split("\n")
            truncated = len(stdout_lines) > self.max_lines
            if truncated:
                stdout = "\n".join(stdout_lines[:self.max_lines])
                stdout += f"\n... (输出截断，共 {len(stdout_lines)} 行，显示前 {self.max_lines} 行)"

            # 收集新生成的图表
            figure_paths = self._collect_new_figures()

            return {
                "success": result.returncode == 0,
                "stdout": stdout,
                "stderr": stderr,
                "error": None if result.returncode == 0 else stderr,
                "truncated": truncated,
                "duration_ms": duration_ms,
                "figure_paths": figure_paths,
            }

        except subprocess.TimeoutExpired:
            duration_ms = int((datetime.now() - start).total_seconds() * 1000)
            return {
                "success": False,
                "stdout": "",
                "stderr": "",
                "error": f"代码执行超时（{self.timeout}s）",
                "truncated": False,
                "duration_ms": duration_ms,
                "figure_paths": [],
            }
        except Exception as e:
            duration_ms = int((datetime.now() - start).total_seconds() * 1000)
            return {
                "success": False,
                "stdout": "",
                "stderr": traceback.format_exc(),
                "error": str(e),
                "truncated": False,
                "duration_ms": duration_ms,
                "figure_paths": [],
            }
        finally:
            self._cleanup_script(script_path)

    def _build_full_code(self, preamble: str, code: str) -> str:
        """组装完整脚本：preamble（不可见）+ 用户代码（截获输出）。"""
        wrapper = f'''
import sys
import io
import traceback
import os
os.chdir(r"{self.sandbox_dir}")

# ── Preamble ──
{preamble}

# ── User Code ──
_capture = io.StringIO()
_original_stdout = sys.stdout
try:
    sys.stdout = _capture
{self._indent_code(code, indent=4)}
finally:
    sys.stdout = _original_stdout
    _output = _capture.getvalue()
    if _output:
        print(_output, end="")
'''
        return wrapper

    @staticmethod
    def _indent_code(code: str, indent: int = 4) -> str:
        """将代码块整体缩进。"""
        prefix = " " * indent
        return "\n".join(prefix + line if line.strip() else "" for line in code.split("\n"))

    def _write_temp_script(self, code: str) -> str:
        """将代码写入临时脚本文件。"""
        script_name = f"_sandbox_{uuid.uuid4().hex[:8]}.py"
        script_path = os.path.join(self.sandbox_dir, script_name)
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code)
        return script_path

    def _cleanup_script(self, path: str):
        """删除临时脚本。"""
        try:
            os.remove(path)
        except OSError:
            pass

    def _collect_new_figures(self) -> list[str]:
        """收集 sandbox 中新生成的图表文件。"""
        figures = []
        if not os.path.isdir(self.sandbox_dir):
            return figures
        for fname in os.listdir(self.sandbox_dir):
            if fname.endswith((".png", ".jpg", ".jpeg", ".svg", ".pdf")):
                figures.append(os.path.join(self.sandbox_dir, fname))
        return sorted(figures)
