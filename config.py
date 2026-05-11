"""
配置模块 —— LLM 模型、路径、执行超时等可调参数集中管理。
支持从 .env 文件加载配置。
"""
import logging
import os
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

try:
    from dotenv import load_dotenv
    # 从项目根目录加载 .env 文件
    _dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.isfile(_dotenv_path):
        load_dotenv(_dotenv_path)
    else:
        load_dotenv()  # 回退到默认搜索
except ImportError:
    pass

logger = logging.getLogger(__name__)

# ── LLM 配置 ──────────────────────────────────────────────
LLM_MODEL: str = os.getenv("DATA_ANALYST_MODEL", "gpt-4o")
LLM_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY") or os.getenv("DATA_ANALYST_API_KEY")
LLM_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "")
LLM_TEMPERATURE: float = float(os.getenv("DATA_ANALYST_TEMPERATURE", "0.1"))
LLM_MAX_TOKENS: int = int(os.getenv("DATA_ANALYST_MAX_TOKENS", "4096"))

# ── 代码沙箱配置 ──────────────────────────────────────────
CODE_TIMEOUT_SEC: int = int(os.getenv("CODE_TIMEOUT_SEC", "60"))
CODE_MAX_OUTPUT_LINES: int = int(os.getenv("CODE_MAX_OUTPUT_LINES", "200"))
SANDBOX_DIR: str = os.getenv(
    "SANDBOX_DIR",
    os.path.join(os.path.dirname(__file__), "sandbox"),
)

# ── 可视化配置 ────────────────────────────────────────────
FIGURE_DIR: str = os.getenv(
    "FIGURE_DIR",
    os.path.join(os.path.dirname(__file__), "figures"),
)
FIGURE_DPI: int = int(os.getenv("FIGURE_DPI", "100"))
FIGURE_FORMAT: str = os.getenv("FIGURE_FORMAT", "png")

# ── 数据限制 ──────────────────────────────────────────────
MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "100"))
MAX_ROWS_DISPLAY: int = int(os.getenv("MAX_ROWS_DISPLAY", "50"))
MAX_COLS_DISPLAY: int = int(os.getenv("MAX_COLS_DISPLAY", "30"))

# ── 重试 & 迭代 ───────────────────────────────────────────
MAX_AGENT_ITERATIONS: int = int(os.getenv("MAX_AGENT_ITERATIONS", "3"))
MAX_WORKFLOW_LOOPS: int = int(os.getenv("MAX_WORKFLOW_LOOPS", "10"))

# ── 自检系统配置 ──────────────────────────────────────────
SELF_INSPECT_DIR: str = os.getenv(
    "SELF_INSPECT_DIR",
    os.path.join(os.path.dirname(__file__), "self_inspect"),
)
SLOW_EXECUTION_THRESHOLD_MS: int = int(os.getenv("SLOW_EXECUTION_THRESHOLD_MS", "30000"))


def ensure_dirs() -> None:
    """确保输出目录存在。"""
    for d in [SANDBOX_DIR, FIGURE_DIR, SELF_INSPECT_DIR]:
        os.makedirs(d, exist_ok=True)
