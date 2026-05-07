"""
配置模块 —— LLM 模型、路径、执行超时等可调参数集中管理。
"""

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── LLM 配置 ──────────────────────────────────────────────
LLM_MODEL = os.getenv("DATA_ANALYST_MODEL", "gpt-4o")
LLM_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
LLM_TEMPERATURE = float(os.getenv("DATA_ANALYST_TEMPERATURE", "0.1"))
LLM_MAX_TOKENS = int(os.getenv("DATA_ANALYST_MAX_TOKENS", "4096"))

# ── 代码沙箱配置 ──────────────────────────────────────────
CODE_TIMEOUT_SEC = int(os.getenv("CODE_TIMEOUT_SEC", "60"))
CODE_MAX_OUTPUT_LINES = int(os.getenv("CODE_MAX_OUTPUT_LINES", "200"))
SANDBOX_DIR = os.getenv("SANDBOX_DIR", os.path.join(os.path.dirname(__file__), "sandbox"))

# ── 可视化配置 ────────────────────────────────────────────
FIGURE_DIR = os.getenv("FIGURE_DIR", os.path.join(os.path.dirname(__file__), "figures"))
FIGURE_DPI = int(os.getenv("FIGURE_DPI", "100"))
FIGURE_FORMAT = os.getenv("FIGURE_FORMAT", "png")

# ── 数据限制 ──────────────────────────────────────────────
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "100"))
MAX_ROWS_DISPLAY = int(os.getenv("MAX_ROWS_DISPLAY", "50"))
MAX_COLS_DISPLAY = int(os.getenv("MAX_COLS_DISPLAY", "30"))

# ── 重试 & 迭代 ───────────────────────────────────────────
MAX_AGENT_ITERATIONS = int(os.getenv("MAX_AGENT_ITERATIONS", "3"))
MAX_WORKFLOW_LOOPS = int(os.getenv("MAX_WORKFLOW_LOOPS", "10"))


def ensure_dirs():
    """确保输出目录存在。"""
    for d in [SANDBOX_DIR, FIGURE_DIR]:
        os.makedirs(d, exist_ok=True)
