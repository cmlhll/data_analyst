#!/usr/bin/env python3
"""
Data Analyst —— 多智能体数据分析系统 CLI。

参考 ChatGPT Advanced Data Analysis 设计，基于 LangGraph 实现。
7 个专业 Agent 通过 Supervisor 路由协作完成端到端数据分析。

用法：
    python main.py <数据文件路径> [--query "分析需求"] [--thread-id "会话ID"]

示例：
    python main.py data/sales.csv
    python main.py data/iris.csv --query "分析品种分类特征，训练分类模型"
    python main.py data/orders.xlsx --query "分析销售趋势并生成报告"
"""

import argparse
import os
import sys

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from tools.file_handler import FileHandler
from graph import run_analysis


def main():
    parser = argparse.ArgumentParser(
        description="Data Analyst - 多智能体数据分析系统 (LangGraph)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py data/sales.csv
  python main.py data/iris.csv --query "特征分类分析 + 训练模型"
  python main.py data.csv --thread-id session-001  # 多轮对话
        """,
    )
    parser.add_argument("file", help="数据文件路径 (CSV/Excel/JSON/Parquet)")
    parser.add_argument("--query", "-q", default="请对这份数据进行全面的数据分析",
                        help="分析需求描述")
    parser.add_argument("--thread-id", "-t", default="default",
                        help="会话标识（用于多轮对话）")

    args = parser.parse_args()

    # ── 1. 校验文件 ──
    print(f"📂 正在检查文件: {args.file}")
    is_valid, err = FileHandler.validate(args.file)
    if not is_valid:
        print(f"❌ 文件校验失败: {err}")
        sys.exit(1)

    print(f"✅ 文件校验通过")
    print(f"\n📋 分析需求: {args.query}")
    print(f"🆔 会话 ID: {args.thread_id}")
    print()

    # ── 2. 确保输出目录 ──
    config.ensure_dirs()

    # ── 3. 运行分析工作流 ──
    try:
        final_state = run_analysis(
            file_path=os.path.abspath(args.file),
            user_query=args.query,
            thread_id=args.thread_id,
        )
    except KeyboardInterrupt:
        print("\n⏹ 用户中断")
        sys.exit(1)

    # ── 4. 输出结果 ──
    print("\n" + "=" * 60)
    print("🎉 分析完成")
    print("=" * 60)

    if final_state.get("report"):
        print("\n📄 最终报告:\n")
        print(final_state["report"])
        # 同时保存报告到文件
        report_path = os.path.join(config.SANDBOX_DIR, "report.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(final_state["report"])
        print(f"\n📝 报告已保存到: {report_path}")

    if final_state.get("figure_paths"):
        print(f"\n📊 生成的图表 ({len(final_state['figure_paths'])} 个):")
        for fp in final_state["figure_paths"]:
            print(f"   - {fp}")

    if final_state.get("error"):
        print(f"\n⚠️  执行中遇到错误: {final_state['error']}")


if __name__ == "__main__":
    main()
