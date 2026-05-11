"""
pipeline.py — 多任务调度器

支持在多个终端中并行运行多个数据分析任务。
每个任务在独立的子进程中执行，有独立的沙箱目录，互不干扰。

用法：
    # 从 JSON 文件读取任务
    python pipeline.py tasks.json --concurrent 3

    # 直接传参
    python pipeline.py --inline '[{"file":"data1.csv","query":"分析销售额趋势"}, ...]' --concurrent 2

    # 用终端同时跑多个独立任务（不同终端各跑一个）
    # 终端 1: python pipeline.py run --task-id task1 --file data1.csv --query "分析A"
    # 终端 2: python pipeline.py run --task-id task2 --file data2.csv --query "分析B"

tasks.json 格式：
    [
        {"task_id": "sales_q1", "file": "/path/to/sales_q1.csv", "query": "分析第一季度销售趋势"},
        {"task_id": "sales_q2", "file": "/path/to/sales_q2.csv", "query": "分析第二季度销售趋势"}
    ]
"""

import argparse
import json
import logging
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

# 确保项目根目录在 path 中
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import config

logger = logging.getLogger(__name__)

# ── 任务定义 ──────────────────────────────────────────────

ANALYSIS_RESULTS_DIR = "analysis_results"


class AnalysisTask:
    """单个分析任务的定义。"""

    def __init__(
        self,
        task_id: str,
        file_path: str,
        user_query: str = "请对这份数据进行全面的数据分析",
        output_dir: Optional[str] = None,
    ) -> None:
        self.task_id = task_id
        self.file_path = os.path.abspath(file_path)
        self.user_query = user_query
        self.output_dir = output_dir or os.path.join(
            _PROJECT_ROOT, ANALYSIS_RESULTS_DIR, task_id
        )

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "file_path": self.file_path,
            "user_query": self.user_query,
            "output_dir": self.output_dir,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AnalysisTask":
        return cls(
            task_id=d["task_id"],
            file_path=d["file_path"],
            user_query=d.get("query", d.get("user_query", "请对这份数据进行全面的数据分析")),
            output_dir=d.get("output_dir"),
        )


# ── 子进程执行函数 ────────────────────────────────────────

def _run_single_task(task_dict: dict) -> dict:
    """
    在子进程中执行单个分析任务。
    这是一个独立函数（不在类中），以便 ProcessPoolExecutor 可以序列化它。

    每个子进程有自己独立的 config 环境（sandbox 等路径被覆写）。
    """
    task = AnalysisTask.from_dict(task_dict)

    # ── 隔离沙箱环境 ─────────────────────────────────────
    # 每个任务用自己的 sandbox 子目录，避免 _working_data.pkl 冲突
    task_sandbox = os.path.join(task.output_dir, "sandbox")
    os.makedirs(task_sandbox, exist_ok=True)
    os.makedirs(task.output_dir, exist_ok=True)

    # 临时覆写配置
    original_sandbox = config.SANDBOX_DIR
    original_figure = config.FIGURE_DIR
    original_self_inspect = config.SELF_INSPECT_DIR
    config.SANDBOX_DIR = task_sandbox
    config.FIGURE_DIR = os.path.join(task.output_dir, "figures")
    config.SELF_INSPECT_DIR = os.path.join(task.output_dir, "self_inspect")

    start_time = time.monotonic()
    result = {
        "task_id": task.task_id,
        "status": "running",
        "file_path": task.file_path,
        "query": task.user_query,
        "error": None,
        "duration_s": 0,
        "report_preview": "",
        "report_path": "",
        "figure_count": 0,
        "issue_count": 0,
    }

    try:
        from graph import run_analysis

        # 执行分析
        final_state = run_analysis(
            file_path=task.file_path,
            user_query=task.user_query,
            thread_id=task.task_id,
        )

        elapsed = time.monotonic() - start_time
        result["duration_s"] = round(elapsed, 1)
        result["status"] = "completed" if not final_state.get("error") else "failed"

        if final_state.get("error"):
            result["error"] = str(final_state["error"][:500])

        # 保存最终报告
        report = final_state.get("report", "")
        if report:
            report_path = os.path.join(task.output_dir, "report.md")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report)
            result["report_path"] = report_path
            result["report_preview"] = report[:300]

        # 统计图表
        figure_paths = final_state.get("figure_paths", [])
        result["figure_count"] = len(figure_paths)

        # 统计问题
        inspection_log = final_state.get("inspection_log", [])
        result["issue_count"] = len(inspection_log)

        # 保存检查点文件
        summary = {
            "task_id": task.task_id,
            "status": result["status"],
            "duration_s": result["duration_s"],
            "error": result["error"],
            "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(os.path.join(task.output_dir, "_summary.json"), "w") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

    except Exception as e:
        elapsed = time.monotonic() - start_time
        result["duration_s"] = round(elapsed, 1)
        result["status"] = "failed"
        result["error"] = f"{type(e).__name__}: {e}"
        import traceback
        logger.exception("Task [%s] 执行异常", task.task_id)
        with open(os.path.join(task.output_dir, "_error.log"), "w") as f:
            f.write(traceback.format_exc())

    finally:
        # 恢复配置
        config.SANDBOX_DIR = original_sandbox
        config.FIGURE_DIR = original_figure
        config.SELF_INSPECT_DIR = original_self_inspect

    return result


# ── 调度器 ────────────────────────────────────────────────

class PipelineScheduler:
    """
    多任务调度器。

    通过 ProcessPoolExecutor 并行执行多个分析任务。
    每个任务在独立子进程中运行，有独立的 sandbox 目录。

    Args:
        max_concurrent: 最大并行任务数
        silent: 是否静默运行（不打印进度）
    """

    def __init__(self, max_concurrent: int = 2, silent: bool = False) -> None:
        self.max_concurrent = max_concurrent
        self.silent = silent
        self.results: list[dict] = []

    def run(self, tasks: list[AnalysisTask]) -> list[dict]:
        """
        并行执行所有任务。

        Args:
            tasks: 分析任务列表

        Returns:
            每个任务的执行结果列表
        """
        n = len(tasks)
        self._log(f"🚀 启动 {n} 个分析任务，最大并行 {self.max_concurrent}")

        task_dicts = [t.to_dict() for t in tasks]
        self.results = []

        with ProcessPoolExecutor(max_workers=self.max_concurrent) as executor:
            future_map = {
                executor.submit(_run_single_task, td): td["task_id"]
                for td in task_dicts
            }

            completed = 0
            for future in as_completed(future_map):
                task_id = future_map[future]
                completed += 1
                try:
                    result = future.result()
                    self.results.append(result)
                    self._print_task_result(result, completed, n)
                except Exception as e:
                    self._log(f"❌ [{task_id}] 任务异常: {e}")
                    self.results.append({
                        "task_id": task_id,
                        "status": "failed",
                        "error": str(e),
                        "duration_s": 0,
                    })

        # 打印汇总
        self._print_summary()
        return self.results

    def _print_task_result(self, result: dict, idx: int, total: int) -> None:
        """打印单个任务结果。"""
        status_emoji = "✅" if result["status"] == "completed" else "❌"
        task_id = result["task_id"]
        duration = result.get("duration_s", 0)
        issues = result.get("issue_count", 0)
        figs = result.get("figure_count", 0)

        line = (
            f"{status_emoji} [{idx}/{total}] {task_id} "
            f"| 耗时: {duration}s | 图表: {figs} | 问题: {issues}"
        )
        if result.get("error"):
            line += f" | 错误: {result['error'][:100]}"

        self._log(line)

    def _print_summary(self) -> None:
        """打印汇总报告。"""
        success = sum(1 for r in self.results if r["status"] == "completed")
        failed = sum(1 for r in self.results if r["status"] == "failed")
        total_time = sum(r.get("duration_s", 0) for r in self.results)
        total_issues = sum(r.get("issue_count", 0) for r in self.results)

        self._log("")
        self._log("=" * 50)
        self._log("📊 多任务执行汇总")
        self._log("=" * 50)
        self._log(f"  总任务: {len(self.results)}")
        self._log(f"  成功: {success} | 失败: {failed}")
        self._log(f"  累计耗时: {total_time:.0f}s")
        self._log(f"  发现问题: {total_issues}")
        self._log("")

        if failed > 0:
            self._log("❌ 失败任务:")
            for r in self.results:
                if r["status"] == "failed":
                    self._log(f"  - [{r['task_id']}]: {r.get('error', '未知错误')}")
            self._log("")

        # 推荐快速查看结果
        self._log("💡 查看单个任务结果:")
        for r in self.results:
            rp = r.get("report_path")
            if rp:
                self._log(f"  cat {rp}")

    def _log(self, msg: str) -> None:
        if not self.silent:
            print(msg)


# ── 单任务命令 (run) ─────────────────────────────────────

def _cmd_run(args: argparse.Namespace) -> None:
    """python pipeline.py run --task-id xxx --file xxx --query xxx"""
    task = AnalysisTask(
        task_id=args.task_id,
        file_path=args.file,
        user_query=args.query,
    )
    os.makedirs(task.output_dir, exist_ok=True)

    print(f"📋 单任务模式: [{task.task_id}]")
    print(f"   文件: {task.file_path}")
    print(f"   查询: {task.user_query}")
    print(f"   输出: {task.output_dir}")
    print()

    result = _run_single_task(task.to_dict())

    status_emoji = "✅" if result["status"] == "completed" else "❌"
    print(f"\n{status_emoji} 任务完成: [{result['task_id']}]")
    print(f"   状态: {result['status']}")
    print(f"   耗时: {result.get('duration_s', 0)}s")
    print(f"   图表: {result.get('figure_count', 0)}")
    print(f"   问题: {result.get('issue_count', 0)}")
    if result.get("report_path"):
        print(f"   报告: {result['report_path']}")
        print()
        print("📄 报告预览:")
        print(result.get("report_preview", "")[:500])


# ── 批量任务命令 (batch) ─────────────────────────────────

def _cmd_batch(args: argparse.Namespace) -> None:
    """python pipeline.py tasks.json --concurrent 3"""
    tasks_file = args.tasks_file
    if not os.path.isfile(tasks_file):
        print(f"❌ 任务文件不存在: {tasks_file}")
        sys.exit(1)

    with open(tasks_file, "r", encoding="utf-8") as f:
        raw_tasks = json.load(f)

    tasks = [AnalysisTask.from_dict(t) for t in raw_tasks]
    print(f"📋 从 {tasks_file} 加载了 {len(tasks)} 个任务")
    print()

    scheduler = PipelineScheduler(max_concurrent=args.concurrent)
    scheduler.run(tasks)


# ── 内联任务命令 (inline) ────────────────────────────────

def _cmd_inline(args: argparse.Namespace) -> None:
    """python pipeline.py --inline '[...]'"""
    raw_tasks = json.loads(args.inline)
    tasks = [AnalysisTask.from_dict(t) for t in raw_tasks]
    print(f"📋 内联指定了 {len(tasks)} 个任务")
    print()

    scheduler = PipelineScheduler(max_concurrent=args.concurrent)
    scheduler.run(tasks)


# ── 查看结果命令 (results) ───────────────────────────────

def _cmd_results(args: argparse.Namespace) -> None:
    """查看历史执行结果。"""
    results_dir = os.path.join(_PROJECT_ROOT, ANALYSIS_RESULTS_DIR)
    if not os.path.isdir(results_dir):
        print("❌ 尚无分析结果")
        return

    tasks = sorted(os.listdir(results_dir))
    if not tasks:
        print("(空)")
        return

    print(f"📋 历史分析结果 ({len(tasks)}):")
    print()
    for task_id in tasks:
        task_dir = os.path.join(results_dir, task_id)
        summary_file = os.path.join(task_dir, "_summary.json")
        if os.path.isfile(summary_file):
            with open(summary_file) as f:
                summary = json.load(f)
            status_emoji = "✅" if summary.get("status") == "completed" else "❌"
            dur = summary.get("duration_s", "?")
            print(f"  {status_emoji} [{task_id}] 耗时: {dur}s")
        else:
            print(f"  ⏳ [{task_id}] (未完成)")

    print()
    print("💡 查看详情: cat analysis_results/<task_id>/report.md")


# ── CLI ──────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Data Analyst 多任务调度器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
用法示例:
  # 1. 多终端模式（每个终端跑一个独立任务）
  python pipeline.py run --task-id t1 --file data1.csv --query "分析A"
  python pipeline.py run --task-id t2 --file data2.csv --query "分析B"

  # 2. 批量模式（一个终端并行跑多个任务）
  python pipeline.py tasks.json --concurrent 3

  # 3. 内联模式（直接传 JSON）
  python pipeline.py --inline '[{"task_id":"s1","file":"a.csv","query":"分析A"}]' --concurrent 2

  # 4. 查看历史结果
  python pipeline.py results

tasks.json 示例:
  [
    {"task_id": "sales_q1", "file": "/path/to/sales_q1.csv", "query": "分析第一季度销售趋势"},
    {"task_id": "sales_q2", "file": "/path/to/sales_q2.csv", "query": "分析第二季度销售趋势"}
  ]
每个任务的结果会保存在 analysis_results/<task_id>/ 目录下。
        """,
    )

    subparsers = parser.add_subparsers(dest="command")

    # run 子命令
    run_parser = subparsers.add_parser("run", help="单任务模式（适合多终端各跑一个）")
    run_parser.add_argument("--task-id", required=True, help="任务唯一标识")
    run_parser.add_argument("--file", required=True, help="数据文件路径")
    run_parser.add_argument("--query", default="请对这份数据进行全面的数据分析", help="分析需求描述")
    run_parser.add_argument("--output-dir", help="输出目录（可选）")

    # results 子命令
    subparsers.add_parser("results", help="查看历史执行结果")

    # 批量模式：直接传 tasks.json 位置参数
    parser.add_argument("tasks_file", nargs="?", help="JSON 任务文件路径")
    parser.add_argument("--inline", help="直接传入 JSON 任务列表")
    parser.add_argument("--concurrent", type=int, default=2, help="最大并行任务数 (默认: 2)")

    args = parser.parse_args()

    if args.command == "run":
        _cmd_run(args)
    elif args.command == "results":
        _cmd_results(args)
    elif args.tasks_file:
        _cmd_batch(args)
    elif args.inline:
        _cmd_inline(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
