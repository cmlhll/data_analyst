#!/usr/bin/env python3
"""
Data Analyst —— 多智能体数据分析系统 CLI。

参考 ChatGPT Advanced Data Analysis 设计，基于 LangGraph 实现。
7 个专业 Agent 通过 Supervisor 路由协作完成端到端数据分析。

支持两种模式：
1. 文件模式: python main.py <数据文件路径> [--query "分析需求"]
2. 数据集模式: python main.py <数据集目录> --query "分析需求"

数据集模式要求目录下包含 metadata.md 文件描述各表结构。
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
  # 文件模式（单个 CSV/Excel 文件）
  python main.py data/iris.csv --query "分析数据特征"

  # 数据集模式（目录中含 metadata.md + 数据文件）
  python main.py data/sales --query "分析客户分布和订单趋势"

  python main.py data/olist --query "分析各州客户分布和订单状态" --thread-id session-001
        """,
    )
    parser.add_argument("target", help="数据文件路径 或 数据集目录(含metadata.md和数据文件)")
    parser.add_argument("--query", "-q", default="请对这份数据进行全面的数据分析",
                        help="分析需求描述")
    parser.add_argument("--thread-id", "-t", default="default",
                        help="会话标识（用于多轮对话）")
    parser.add_argument("--dataset", action="store_true",
                        help="强制使用数据集模式（即使target不是目录）")

    args = parser.parse_args()

    target = os.path.abspath(args.target)
    is_dataset = args.dataset or os.path.isdir(target)

    if is_dataset:
        # ── 数据集模式 ──
        if not os.path.isdir(target):
            print(f"❌ 数据集目录不存在: {target}")
            sys.exit(1)

        meta_path = os.path.join(target, "metadata.md")
        if not os.path.isfile(meta_path):
            print(f"❌ 数据集目录缺少 metadata.md: {meta_path}")
            sys.exit(1)

        print(f"📂 数据集: {target}")
        print(f"📋 分析需求: {args.query}")
        print(f"🆔 会话 ID: {args.thread_id}")
        print()

        # 确保输出目录
        config.ensure_dirs()

        try:
            final_state = run_analysis(
                dataset_dir=target,
                user_query=args.query,
                thread_id=args.thread_id,
            )
        except KeyboardInterrupt:
            print("\n⏹ 用户中断")
            sys.exit(1)
    else:
        # ── 文件模式（原有逻辑） ──
        print(f"📂 正在检查文件: {target}")
        is_valid, err = FileHandler.validate(target)
        if not is_valid:
            print(f"❌ 文件校验失败: {err}")
            sys.exit(1)

        print(f"✅ 文件校验通过")
        print(f"\n📋 分析需求: {args.query}")
        print(f"🆔 会话 ID: {args.thread_id}")
        print()

        # 确保输出目录
        config.ensure_dirs()

        try:
            final_state = run_analysis(
                file_path=target,
                user_query=args.query,
                thread_id=args.thread_id,
            )
        except KeyboardInterrupt:
            print("\n⏹ 用户中断")
            sys.exit(1)

    # ── 输出结果 ──
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
