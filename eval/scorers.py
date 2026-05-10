"""Rule-based scorers for data_analyst eval."""
from __future__ import annotations

import re
from typing import Any


def _text(state: dict[str, Any]) -> str:
    parts = [state.get('report', ''), state.get('last_output', '')]
    for h in state.get('code_history', []):
        parts.append(h.get('output', ''))
        parts.append(h.get('code', ''))
    return '\n'.join(str(p) for p in parts if p)


def score_keywords(text: str, keywords: list[str]) -> tuple[float, list[str]]:
    if not keywords:
        return 1.0, []
    # 智能关键词匹配：支持日期格式宽松匹配
    def _matches(text, keyword):
        if keyword in text:
            return True
        # 日期格式宽松匹配：2026-04-19 匹配 "4月19日"、"19日"、"04月19"
        date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', keyword)
        if date_match:
            y, m, d = date_match.groups()
            # 匹配 "4月19日"、"04月19日"、"19日" 等格式
            patterns = [
                f'{y}年{m.lstrip("0")}月{d.lstrip("0")}日',
                f'{m.lstrip("0")}月{d.lstrip("0")}日',
                f'{int(m)}月{int(d)}日',
                f'{int(d)}日',
                f'{y}-{m}-{d}',
            ]
            for p in patterns:
                if p in text:
                    return True
        return False
    missing = [k for k in keywords if k and not _matches(text, k)]
    return (len(keywords) - len(missing)) / len(keywords), missing


def score_agents(state: dict[str, Any], required: list[str]) -> tuple[float, list[str]]:
    used = {h.get('agent') for h in state.get('code_history', [])}
    if state.get('report'):
        used.add('reporter')
    missing = [a for a in required if a not in used]
    if not required:
        return 1.0, []
    return (len(required) - len(missing)) / len(required), missing


def score_execution(state: dict[str, Any]) -> tuple[float, list[str]]:
    history = state.get('code_history', [])
    if not history:
        return 0.0, ['no_code_history']
    failed = [h.get('agent', 'unknown') for h in history if not h.get('success', False)]
    if failed:
        return max(0.0, 1 - len(failed) / len(history)), failed
    return 1.0, []


def score_visualization(state: dict[str, Any], query: str) -> tuple[float, list[str]]:
    need = any(w in query for w in ['图', '可视化', '趋势', '分布'])
    if not need:
        return 1.0, []
    figs = state.get('figure_paths', [])
    return (1.0, []) if figs else (0.0, ['missing_figure'])


def score_ml(state: dict[str, Any], query: str) -> tuple[float, list[str]]:
    need = any(w.lower() in query.lower() for w in ['模型', '分类', '回归', '预测', 'model'])
    if not need:
        return 1.0, []
    text = _text(state).lower()
    hits = [w for w in ['accuracy', 'auc', 'f1', 'precision', 'recall', '模型', '准确'] if w.lower() in text]
    return (1.0, []) if hits else (0.2, ['missing_ml_metrics'])


def score_case(case: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    text = _text(state)
    kw_score, missing_kw = score_keywords(text, case.get('expected_keywords', []))
    agent_score, missing_agents = score_agents(state, case.get('required_agents', []))
    exec_score, failed_agents = score_execution(state)
    viz_score, viz_issues = score_visualization(state, case.get('query', ''))
    ml_score, ml_issues = score_ml(state, case.get('query', ''))
    error_penalty = 0.2 if state.get('error') else 0.0
    final = max(0.0, kw_score * 0.35 + agent_score * 0.25 + exec_score * 0.2 + viz_score * 0.1 + ml_score * 0.1 - error_penalty)
    issues = []
    if missing_kw:
        issues.append({'type': 'missing_keywords', 'items': missing_kw})
    if missing_agents:
        issues.append({'type': 'missing_agents', 'items': missing_agents})
    if failed_agents:
        issues.append({'type': 'failed_agents', 'items': failed_agents})
    if viz_issues:
        issues.append({'type': 'visualization', 'items': viz_issues})
    if ml_issues:
        issues.append({'type': 'ml', 'items': ml_issues})
    return {
        'case_id': case.get('case_id', case.get('dataset_id')),
        'dataset_id': case.get('dataset_id'),
        'score': round(final, 4),
        'subscores': {'keywords': kw_score, 'agents': agent_score, 'execution': exec_score, 'visualization': viz_score, 'ml': ml_score},
        'issues': issues,
        'report_preview': state.get('report', '')[:500],
    }
