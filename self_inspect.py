"""
自检系统 —— 多 Agent 数据分析工作流的执行过程监控、问题记录与事后分析。

功能：
1. record_issue() — 执行过程中记录问题（耗时慢、代码失败、数据异常等）
2. PostMortemAnalyzer — 执行完后自动分析日志，生成优化报告
3. 持久化存储：self_inspect/history.jsonl + 每次报告的 .md 文件
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

import config

logger = logging.getLogger(__name__)

# ── 问题分类 ──────────────────────────────────────────────
ISSUE_CATEGORIES = {
    "EXECUTION_SLOW",    # 执行速度慢（超过阈值）
    "CODE_FAILURE",      # 代码执行失败
    "DATA_LOAD_ERROR",   # 数据加载异常
    "LOGIC_ISSUE",       # 逻辑混乱 / 分析结果不合理
    "MEMORY_HIGH",       # 内存占用过高
    "UNEXPECTED_NULL",   # 意外的空值 / NaN
}

SEVERITY_LEVELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def record_issue(
    state: dict,
    category: str,
    severity: str,
    detail: str,
    agent_name: Optional[str] = None,
    duration_ms: Optional[float] = None,
) -> dict:
    """
    创建一个问题记录，追加到 state['inspection_log'] 并写入 history.jsonl。

    Args:
        state: 当前 DataAnalysisState（会原地修改）
        category: 问题分类（ISSUE_CATEGORIES 之一）
        severity: 严重程度（LOW / MEDIUM / HIGH / CRITICAL）
        detail: 详细描述
        agent_name: 产生问题的 Agent 名称
        duration_ms: 执行耗时（毫秒）

    Returns:
        创建的问题记录 dict
    """
    if category not in ISSUE_CATEGORIES:
        raise ValueError(f"未知问题分类: {category!r}，可选: {ISSUE_CATEGORIES}")
    if severity not in SEVERITY_LEVELS:
        raise ValueError(f"未知严重程度: {severity!r}，可选: {SEVERITY_LEVELS}")

    issue: dict[str, Any] = {
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "category": category,
        "severity": severity,
        "detail": detail,
        "agent": agent_name,
        "duration_ms": duration_ms,
    }

    # 追加到 state
    log = state.setdefault("inspection_log", [])
    log.append(issue)

    # 持久化到 JSONL
    _append_to_jsonl(issue)
    return issue


def _append_to_jsonl(issue: dict) -> None:
    """追加一条记录到 history.jsonl。"""
    os.makedirs(config.SELF_INSPECT_DIR, exist_ok=True)
    filepath = os.path.join(config.SELF_INSPECT_DIR, "history.jsonl")
    try:
        with open(filepath, "a", encoding="utf-8") as f:
            json.dump(issue, f, ensure_ascii=False)
            f.write("\n")
    except OSError:
        logger.exception("写入问题记录失败: %s", filepath)


def load_history(limit: int = 100) -> list[dict]:
    """加载 history.jsonl 中最近的记录。"""
    filepath = os.path.join(config.SELF_INSPECT_DIR, "history.jsonl")
    if not os.path.isfile(filepath):
        return []
    records = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    except (OSError, json.JSONDecodeError):
        logger.exception("读取 history.jsonl 失败")
    return records[-limit:]


# ── 事后分析器 ────────────────────────────────────────────

class PostMortemAnalyzer:
    """
    事后分析器：读取当前运行的问题日志，生成结构化的优化建议报告。
    """

    def __init__(self, session_id: str = "default") -> None:
        self.session_id = session_id
        self.dir = config.SELF_INSPECT_DIR

    def analyze_and_save(self, inspection_log: list[dict]) -> dict:
        """
        入口：分析问题日志 → 生成报告 → 保存文件。

        Args:
            inspection_log: 本次运行的问题记录列表

        Returns:
            {"report": str, "report_path": str | None, "summary": dict}
        """
        # 统计摘要
        summary = {
            "total": len(inspection_log),
            "by_category": {},
            "by_severity": {},
            "by_agent": {},
        }
        for issue in inspection_log:
            cat = issue.get("category", "UNKNOWN")
            summary["by_category"][cat] = summary["by_category"].get(cat, 0) + 1
            sev = issue.get("severity", "UNKNOWN")
            summary["by_severity"][sev] = summary["by_severity"].get(sev, 0) + 1
            agent = issue.get("agent", "UNKNOWN") or "UNKNOWN"
            summary["by_agent"][agent] = summary["by_agent"].get(agent, 0) + 1

        # 生成报告
        report = self._generate_report(inspection_log, summary)
        report_path = self._save_report(report)

        return {
            "report": report,
            "report_path": report_path,
            "summary": summary,
        }

    def _generate_report(self, log: list[dict], summary: dict) -> str:
        """生成 Markdown 格式的优化报告。"""
        lines = []

        lines.append("# 📊 分析工作流自检报告")
        lines.append("")
        lines.append(f"**会话 ID:** {self.session_id}")
        lines.append(f"**生成时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**记录问题数:** {summary['total']}")
        lines.append("")
        lines.append("---")
        lines.append("")

        if summary["total"] == 0:
            lines.append("✅ **本次分析没有记录到任何问题，执行顺利！**")
            lines.append("")
            return "\n".join(lines)

        # 概览
        lines.append("## 📈 概览统计")
        lines.append("")
        lines.append("| 维度 | 统计 |")
        lines.append("|------|------|")
        lines.append(f"| 按分类 | {', '.join(f'{k}: {v}' for k, v in summary['by_category'].items())} |")
        lines.append(f"| 按严重程度 | {', '.join(f'{k}: {v}' for k, v in summary['by_severity'].items())} |")
        lines.append(f"| 按 Agent | {', '.join(f'{k}: {v}' for k, v in summary['by_agent'].items())} |")
        lines.append("")

        # 按严重程度排序，逐条分析
        lines.append("## 🔍 问题明细与优化建议")
        lines.append("")

        # 先按严重程度排序
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        sorted_log = sorted(log, key=lambda x: severity_order.get(x.get("severity", "LOW"), 99))

        for i, issue in enumerate(sorted_log, 1):
            category = issue.get("category", "UNKNOWN")
            severity = issue.get("severity", "LOW")
            agent = issue.get("agent", "N/A") or "N/A"
            detail = issue.get("detail", "")
            duration = issue.get("duration_ms")

            sev_emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}
            emoji = sev_emoji.get(severity, "⚪")

            lines.append(f"### {emoji} 问题 {i}: {category}")
            lines.append(f"- **严重程度:** {severity}")
            lines.append(f"- **Agent:** {agent}")
            if duration is not None:
                lines.append(f"- **耗时:** {duration:.0f}ms")
            lines.append(f"- **详情:** {detail}")
            lines.append("")

            # 优化建议
            suggestion = self._get_suggestion(category, severity, detail)
            lines.append(f"> 💡 **优化建议:** {suggestion}")
            lines.append("")

        # 长期的改进建议
        lines.append("---")
        lines.append("")
        lines.append("## 🎯 长期优化方向")
        lines.append("")
        suggestions = self._get_longterm_suggestions(summary)
        for s in suggestions:
            lines.append(f"- {s}")
        lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _get_suggestion(category: str, severity: str, detail: str) -> str:
        """根据问题分类和严重程度给出优化建议。"""
        suggestions = {
            "EXECUTION_SLOW": (
                "考虑优化数据集大小（采样/分块处理），"
                "或增加 config.CODE_TIMEOUT_SEC / SLOW_EXECUTION_THRESHOLD_MS。"
                "对于大型数据集，建议使用更高效的算法（如向量化操作替代循环）。"
            ),
            "CODE_FAILURE": (
                "检查 LLM 生成的代码是否有语法错误或逻辑问题。"
                "建议在 system prompt 中增加代码质量约束。"
                "也可以考虑增加重试机制（当前只执行一次）。"
            ),
            "DATA_LOAD_ERROR": (
                "检查数据文件格式是否正确，或文件是否损坏。"
                "建议在 data_loader 中增加格式检测和降级读取策略。"
            ),
            "LOGIC_ISSUE": (
                "检查提示词中分析逻辑的描述是否清晰。"
                "建议在 system prompt 中增加分析步骤的具体指导。"
            ),
            "MEMORY_HIGH": (
                "数据集可能过大。建议增加采样策略，"
                "或使用 chunksize 分块读取。"
                "可以考虑使用更轻量级的数据结构。"
            ),
            "UNEXPECTED_NULL": (
                "检查数据清洗步骤是否充分。"
                "建议在 data_cleaner 中增加更全面的缺失值检测和填充策略。"
            ),
        }
        return suggestions.get(category, "建议检查 Agent 提示词和配置参数。")

    @staticmethod
    def _get_longterm_suggestions(summary: dict) -> list[str]:
        """基于统计摘要生成长期改进方向。"""
        suggestions = []

        by_category = summary.get("by_category", {})
        total = summary.get("total", 0)

        if by_category.get("EXECUTION_SLOW", 0) > 0:
            suggestions.append(
                "🕐 **执行速度优化:** 频繁出现执行慢的问题。"
                "建议对小数据集做性能基准测试，考虑预计算或缓存机制。"
            )
        if by_category.get("CODE_FAILURE", 0) > 0:
            suggestions.append(
                "🐛 **代码可靠性:** 代码失败频率较高。"
                "建议增加 LLM 代码生成的测试预览环节，或启用代码审查。"
            )
        if by_category.get("DATA_LOAD_ERROR", 0) > 0:
            suggestions.append(
                "📁 **数据加载鲁棒性:** 增强多格式文件的兼容性处理。"
            )
        if total > 10:
            suggestions.append(
                "📊 **整体健康度:** 问题数量较多（共 {} 个），"
                "建议定期查看 self_inspect/ 目录下的历史报告，制定改进计划。".format(total)
            )

        if not suggestions:
            suggestions.append("继续关注！可以在 config.py 中调整阈值来捕获更细粒度的问题。")

        return suggestions

    def _save_report(self, report: str) -> str:
        """保存报告到文件，返回文件路径。"""
        os.makedirs(self.dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"report_{self.session_id}_{ts}.md"
        filepath = os.path.join(self.dir, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(report)
        except OSError:
            logger.exception("保存自检报告失败: %s", filepath)
            return ""
        logger.info("自检报告已保存: %s", filepath)
        return filepath
