"""
代码沙箱执行器 —— 安全执行 LLM 生成的 Python 代码，捕获输出与异常。
包含 AST 安全检查，拒绝危险操作。
"""
import ast
import glob
import logging
import os
import re
import subprocess
import sys
import traceback
import uuid
from datetime import datetime
from typing import Any

import config

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """AST 安全检查发现危险代码时抛出。"""
    pass


class _SafetyInjector:
    """
    生成 AST 安全检查代码，注入到执行脚本的 preamble 和 user code 之间。
    """

    FORBIDDEN_IMPORTS = {'subprocess', 'shutil', 'socket', 'ctypes'}
    FORBIDDEN_CALLS = {
        'os.system', 'os.popen', 'os.exec', 'os.execv', 'os.execl',
        'os.execve', 'os.execle', 'os.execvp', 'os.execvpe',
        'subprocess.run', 'subprocess.call', 'subprocess.Popen',
        'subprocess.check_call', 'subprocess.check_output',
        'shutil.rmtree', 'shutil.move', 'shutil.copy', 'shutil.copytree',
    }

    @classmethod
    def build_safety_wrapper(cls, sandbox_dir: str, root_dir: str) -> str:
        return f'''
import ast as _ast
import os as _os
import sys as _sys

_SANDBOX_DIR = {sandbox_dir!r}
_ROOT_DIR = {root_dir!r}
_FORBIDDEN_IMPORTS = {cls.FORBIDDEN_IMPORTS!r}
_FORBIDDEN_CALLS = {cls.FORBIDDEN_CALLS!r}

class _SecurityVisitor(_ast.NodeVisitor):
    def visit_Import(self, node):
        for alias in node.names:
            top = alias.name.split(".")[0]
            if top in _FORBIDDEN_IMPORTS:
                raise PermissionError(f"Security: forbidden import '{{alias.name}}'")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            top = node.module.split(".")[0]
            if top in _FORBIDDEN_IMPORTS:
                raise PermissionError(f"Security: forbidden import from '{{node.module}}'")
        self.generic_visit(node)

    def visit_Call(self, node):
        # Check dotted calls like os.system(...)
        if isinstance(node.func, _ast.Attribute):
            parts = []
            obj = node.func
            while isinstance(obj, _ast.Attribute):
                parts.append(obj.attr)
                obj = obj.value
            if isinstance(obj, _ast.Name):
                parts.append(obj.id)
                full = ".".join(reversed(parts))
                if full in _FORBIDDEN_CALLS:
                    raise PermissionError(f"Security: forbidden call '{{full}}()'")
        # Check built-in eval/exec/compile
        elif isinstance(node.func, _ast.Name):
            if node.func.id in ("eval", "exec", "compile"):
                raise PermissionError(f"Security: forbidden built-in '{{node.func.id}}()'")
            # Check open() writing outside sandbox/root
            if node.func.id == "open" and node.args:
                mode = "r"
                if len(node.args) > 1 and isinstance(node.args[1], _ast.Constant):
                    mode = str(node.args[1].value)
                if "w" in mode or "a" in mode or "+" in mode:
                    if isinstance(node.args[0], _ast.Constant):
                        fpath = str(node.args[0].value)
                        abspath = _os.path.abspath(fpath)
                        if not (abspath.startswith(_SANDBOX_DIR) or abspath.startswith(_ROOT_DIR)):
                            raise PermissionError(f"Security: writing outside project: '{{fpath}}'")
        self.generic_visit(node)

def _run_safety_check(user_code: str) -> None:
    try:
        tree = _ast.parse(user_code)
    except SyntaxError as e:
        raise PermissionError(f"Security: syntax error in code: {{e}}")
    _SecurityVisitor().visit(tree)
'''
    @staticmethod
    def danger_prefix() -> str:
        return "# --- SAFETY CHECK ---"


class CodeExecutor:
    """
    在子进程中执行 Python 代码，提供：
    - AST 安全检查（拒绝危险模块/调用）
    - 超时控制（config.CODE_TIMEOUT_SEC）
    - stdout/stderr 捕获
    - 输出行数截断
    - 临时目录清理
    - 自动收集新生成的图表文件
    """

    def __init__(self) -> None:
        config.ensure_dirs()
        self.sandbox_dir = config.SANDBOX_DIR
        self.timeout = config.CODE_TIMEOUT_SEC
        self.max_lines = config.CODE_MAX_OUTPUT_LINES
        self.project_root = os.path.realpath(
            os.path.join(os.path.dirname(__file__), '..')
        )
        self._safety_code = _SafetyInjector.build_safety_wrapper(
            self.sandbox_dir, self.project_root
        )

    def reset_working_data(self) -> None:
        """跨 case 清理沙箱中的工作数据和图片，保留临时脚本。"""
        patterns = ['*.pkl', '*.png', '*.jpg', '*.jpeg', '*.svg', '*.pdf']
        for pattern in patterns:
            for fpath in glob.glob(os.path.join(self.sandbox_dir, pattern)):
                try:
                    os.remove(fpath)
                except OSError:
                    pass

    def execute(self, code: str, preamble: str = "") -> dict[str, Any]:
        """
        执行代码并返回结构化结果。

        Args:
            code: 要执行的 Python 代码（LLM 生成，会经过 AST 安全检查）
            preamble: 前置代码（如 import、数据加载），不受安全检查

        Returns:
            {
                "success": bool,
                "stdout": str,
                "stderr": str,
                "error": str | None,
                "truncated": bool,
                "duration_ms": int,
                "figure_paths": list[str],
            }
        """
        full_code = self._build_full_code(preamble, code)
        script_path = self._write_temp_script(full_code)

        start = datetime.now()
        try:
            logger.info("Executing code in sandbox: %s", self.sandbox_dir)
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

            logger.info("Exit code: %d, duration: %dms", result.returncode, duration_ms)
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
            logger.warning("Execution timed out after %ds", self.timeout)
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
            logger.exception("Execution exception")
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
        """
        组装完整脚本：
        1. preamble（导入、数据加载）
        2. inline safety check（对 user code 做 AST 分析）
        3. user code（stdout 捕获执行）
        4. inter-agent persistence（自动保存修改后的 df）
        """
        safety_check = self._safety_code
        user_code_repr = repr(code)

        wrapper = f'''
import sys
import io
import traceback
import os
os.chdir(r"{self.sandbox_dir}")

# ── Preamble ──
{preamble}

# ── Safety Check ──
{safety_check}
_run_safety_check({user_code_repr})

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

# ── Inter-Agent Persistence: save modified df ──
try:
    _df_maybe = locals().get('df')
    if _df_maybe is None:
        _df_maybe = globals().get('df')
    if _df_maybe is not None:
        import pandas as _pd_check
        if isinstance(_df_maybe, _pd_check.DataFrame):
            _df_maybe.to_pickle('_working_data.pkl')
except Exception:
    pass  # best-effort: don't crash the script
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

    def _cleanup_script(self, path: str) -> None:
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
