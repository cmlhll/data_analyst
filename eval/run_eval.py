"""Run offline benchmark for data_analyst.

Default mode is mock, which does not call LLM and is safe for CI.
Use --mode agent to run the real LangGraph pipeline through graph.run_analysis.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.fixture_generator import generate_all
from eval.mock_runner import run_mock
from eval.scorers import score_case


def load_cases(path: Path) -> list[dict]:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def run_agent(case: dict) -> dict:
    from graph import run_analysis
    return run_analysis(file_path=str(ROOT / case['file_path']), user_query=case['query'], thread_id=f"eval-{case.get('case_id', case['dataset_id'])}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['mock', 'agent'], default='mock')
    parser.add_argument('--output-dir', default='eval/results')
    parser.add_argument('--fail-under', type=float, default=0.75)
    args = parser.parse_args()

    data_dir = ROOT / 'eval' / 'generated_data'
    generate_all(data_dir)
    cases = load_cases(data_dir / 'cases.json')

    results = []
    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {case.get('dataset_id')} :: {case.get('query')}")
        state = run_mock(case) if args.mode == 'mock' else run_agent(case)
        results.append(score_case(case, state))

    out = ROOT / args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    result_path = out / f'{args.mode}_eval_results.json'
    report_path = out / f'{args.mode}_eval_report.md'
    result_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')

    avg = sum(r['score'] for r in results) / len(results)
    lines = ['# data_analyst Eval Report', '', f'- mode: {args.mode}', f'- cases: {len(results)}', f'- average_score: {avg:.4f}', '']
    lines += ['| case_id | dataset | score | issues |', '|---|---|---:|---|']
    for r in results:
        issues = '; '.join(i['type'] for i in r['issues']) or '-'
        lines.append(f"| {r['case_id']} | {r['dataset_id']} | {r['score']:.4f} | {issues} |")
    report_path.write_text('\n'.join(lines), encoding='utf-8')

    print(f"results: {result_path}")
    print(f"report: {report_path}")
    print(f"average_score={avg:.4f}")
    return 0 if avg >= args.fail_under else 2


if __name__ == '__main__':
    raise SystemExit(main())
