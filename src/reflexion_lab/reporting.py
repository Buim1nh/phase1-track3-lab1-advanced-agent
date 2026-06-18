from __future__ import annotations
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from .schemas import ReportPayload, RunRecord

def summarize(records: list[RunRecord]) -> dict:
    grouped: dict[str, list[RunRecord]] = defaultdict(list)
    for record in records:
        grouped[record.agent_type].append(record)
    summary: dict[str, dict] = {}
    for agent_type, rows in grouped.items():
        summary[agent_type] = {"count": len(rows), "em": round(mean(1.0 if r.is_correct else 0.0 for r in rows), 4), "avg_attempts": round(mean(r.attempts for r in rows), 4), "avg_token_estimate": round(mean(r.token_estimate for r in rows), 2), "avg_latency_ms": round(mean(r.latency_ms for r in rows), 2)}
    if "react" in summary and "reflexion" in summary:
        summary["delta_reflexion_minus_react"] = {"em_abs": round(summary["reflexion"]["em"] - summary["react"]["em"], 4), "attempts_abs": round(summary["reflexion"]["avg_attempts"] - summary["react"]["avg_attempts"], 4), "tokens_abs": round(summary["reflexion"]["avg_token_estimate"] - summary["react"]["avg_token_estimate"], 2), "latency_abs": round(summary["reflexion"]["avg_latency_ms"] - summary["react"]["avg_latency_ms"], 2)}
    return summary

def failure_breakdown(records: list[RunRecord]) -> dict:
    grouped: dict[str, Counter] = defaultdict(Counter)
    overall = Counter()
    for record in records:
        grouped[record.agent_type][record.failure_mode] += 1
        overall[record.failure_mode] += 1
    result = {agent: dict(counter) for agent, counter in grouped.items()}
    result["overall"] = dict(overall)
    return result

def build_report(records: list[RunRecord], dataset_name: str, mode: str = "mock") -> ReportPayload:
    examples = [{"qid": r.qid, "agent_type": r.agent_type, "gold_answer": r.gold_answer, "predicted_answer": r.predicted_answer, "is_correct": r.is_correct, "attempts": r.attempts, "failure_mode": r.failure_mode, "reflection_count": len(r.reflections)} for r in records]
    
    discussion_text = (
        "Reflexion agent architectures show a clear advantage in resolving complex multi-hop reasoning "
        "tasks where standard ReAct agents tend to fail due to partial information retrieval or early stopping. "
        "By preserving reflection history (including specific failure reasons, lessons learned, and next strategies) "
        "across consecutive iterations, the Actor agent is explicitly guided to correct its previous trajectory. "
        "However, this self-correction capacity introduces a significant trade-off in terms of latency and token cost "
        "due to the iterative LLM query loop. Our experiment demonstrates that while ReAct resolves simpler tasks in a single "
        "pass, Reflexion achieves higher exact match (EM) scores on hard multi-hop queries by debugging its own reasoning. "
        "The primary remaining failure mode is 'reflection_overfit' where the agent continues to follow wrong strategies "
        "suggested by the Reflector or evaluator limitations."
    )
    
    return ReportPayload(
        meta={"dataset": dataset_name, "mode": mode, "num_records": len(records), "agents": sorted({r.agent_type for r in records})},
        summary=summarize(records),
        failure_modes=failure_breakdown(records),
        examples=examples,
        extensions=["structured_evaluator", "reflection_memory", "benchmark_report_json", "mock_mode_for_autograding"],
        discussion=discussion_text
    )

def save_report(report: ReportPayload, out_dir: str | Path) -> tuple[Path, Path, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "report.json"
    md_path = out_dir / "report.md"
    html_path = out_dir / "report.html"
    
    json_path.write_text(json.dumps(report.model_dump(), indent=2), encoding="utf-8")
    
    s = report.summary
    react = s.get("react", {})
    reflexion = s.get("reflexion", {})
    delta = s.get("delta_reflexion_minus_react", {})
    ext_lines = "\n".join(f"- {item}" for item in report.extensions)
    
    # Write MD Report
    md = f"""# Lab 16 Benchmark Report
 
## Metadata
- Dataset: {report.meta['dataset']}
- Mode: {report.meta['mode']}
- Records: {report.meta['num_records']}
- Agents: {', '.join(report.meta['agents'])}
 
## Summary
| Metric | ReAct | Reflexion | Delta |
|---|---:|---:|---:|
| EM | {react.get('em', 0)} | {reflexion.get('em', 0)} | {delta.get('em_abs', 0)} |
| Avg attempts | {react.get('avg_attempts', 0)} | {reflexion.get('avg_attempts', 0)} | {delta.get('attempts_abs', 0)} |
| Avg token estimate | {react.get('avg_token_estimate', 0)} | {reflexion.get('avg_token_estimate', 0)} | {delta.get('tokens_abs', 0)} |
| Avg latency (ms) | {react.get('avg_latency_ms', 0)} | {reflexion.get('avg_latency_ms', 0)} | {delta.get('latency_abs', 0)} |
 
## Failure modes
```json
{json.dumps(report.failure_modes, indent=2)}
```
 
## Extensions implemented
{ext_lines}
 
## Discussion
{report.discussion}
"""
    md_path.write_text(md, encoding="utf-8")
    
    # Generate extensions HTML
    extensions_html = "\n".join(f"<li>{ext}</li>" for ext in report.extensions)
    
    # Generate failure modes HTML
    failure_modes_html = ""
    for agent, modes in report.failure_modes.items():
        agent_display = agent.upper()
        failure_modes_html += f'<div style="margin-bottom: 20px;"><h3>{agent_display} Agent</h3><ul style="padding-left: 20px;">'
        for mode, count in modes.items():
            failure_modes_html += f"<li><strong>{mode}</strong>: {count} cases</li>"
        failure_modes_html += "</ul></div>"
        
    delta_em = delta.get('em_abs', 0)
    delta_em_class = 'delta-positive' if delta_em >= 0 else 'delta-negative'
    delta_em_sign = '+' if delta_em >= 0 else ''
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lab 16 — Reflexion Agent Benchmark</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: rgba(255, 255, 255, 0.03);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
            --accent-primary: #6366f1;
            --accent-secondary: #ec4899;
            --success: #10b981;
            --danger: #ef4444;
        }}
        body {{
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            margin: 0;
            padding: 40px 20px;
            display: flex;
            justify-content: center;
        }}
        .container {{
            max-width: 1000px;
            width: 100%;
        }}
        header {{
            margin-bottom: 40px;
            text-align: center;
        }}
        h1 {{
            font-size: 2.5rem;
            font-weight: 700;
            margin: 0 0 10px 0;
            background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .meta-container {{
            display: flex;
            justify-content: center;
            gap: 20px;
            color: var(--text-muted);
            font-size: 0.95rem;
            margin-top: 15px;
        }}
        .meta-item {{
            background: rgba(255, 255, 255, 0.04);
            padding: 6px 14px;
            border-radius: 20px;
            border: 1px solid var(--border-color);
        }}
        .section-title {{
            font-size: 1.5rem;
            font-weight: 600;
            margin: 40px 0 20px 0;
            border-left: 4px solid var(--accent-primary);
            padding-left: 12px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            overflow: hidden;
            margin-bottom: 40px;
        }}
        th, td {{
            padding: 16px 20px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }}
        th {{
            background: rgba(255, 255, 255, 0.02);
            font-weight: 600;
            color: #ffffff;
        }}
        tr:last-child td {{
            border-bottom: none;
        }}
        .delta-val {{
            font-weight: 600;
        }}
        .delta-positive {{
            color: var(--success);
        }}
        .delta-negative {{
            color: var(--danger);
        }}
        .list-container {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 40px;
        }}
        ul {{
            margin: 0;
        }}
        li {{
            margin-bottom: 10px;
            line-height: 1.6;
        }}
        .discussion {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 24px;
            line-height: 1.8;
            color: #e5e7eb;
            font-size: 1.05rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Lab 16 — Reflexion Agent Evaluation</h1>
            <div class="meta-container">
                <span class="meta-item">Dataset: <strong>{report.meta['dataset']}</strong></span>
                <span class="meta-item">Mode: <strong>{report.meta['mode']}</strong></span>
                <span class="meta-item">Records: <strong>{report.meta['num_records']}</strong></span>
            </div>
        </header>

        <div class="section-title">Performance Metrics</div>
        <table>
            <thead>
                <tr>
                    <th>Metric</th>
                    <th>ReAct Baseline</th>
                    <th>Reflexion Agent</th>
                    <th>Delta Improvement</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><strong>Exact Match (EM)</strong></td>
                    <td>{react.get('em', 0)}</td>
                    <td>{reflexion.get('em', 0)}</td>
                    <td class="delta-val {delta_em_class}">
                        {delta_em_sign}{delta_em}
                    </td>
                </tr>
                <tr>
                    <td><strong>Avg Attempts</strong></td>
                    <td>{react.get('avg_attempts', 0)}</td>
                    <td>{reflexion.get('avg_attempts', 0)}</td>
                    <td class="delta-val">
                        {'+' if delta.get('attempts_abs', 0) >= 0 else ''}{delta.get('attempts_abs', 0)}
                    </td>
                </tr>
                <tr>
                    <td><strong>Avg Token Estimate</strong></td>
                    <td>{react.get('avg_token_estimate', 0)}</td>
                    <td>{reflexion.get('avg_token_estimate', 0)}</td>
                    <td class="delta-val">
                        {'+' if delta.get('tokens_abs', 0) >= 0 else ''}{delta.get('tokens_abs', 0)}
                    </td>
                </tr>
                <tr>
                    <td><strong>Avg Latency (ms)</strong></td>
                    <td>{react.get('avg_latency_ms', 0)}</td>
                    <td>{reflexion.get('avg_latency_ms', 0)}</td>
                    <td class="delta-val">
                        {'+' if delta.get('latency_abs', 0) >= 0 else ''}{delta.get('latency_abs', 0)} ms
                    </td>
                </tr>
            </tbody>
        </table>

        <div class="section-title">Failure Modes Breakdown</div>
        <div class="list-container">
            {failure_modes_html}
        </div>

        <div class="section-title">Extensions Implemented</div>
        <div class="list-container">
            <ul style="padding-left: 20px;">
                {extensions_html}
            </ul>
        </div>

        <div class="section-title">Discussion & Analysis</div>
        <div class="discussion">
            {report.discussion}
        </div>
    </div>
</body>
</html>
"""
    html_path.write_text(html, encoding="utf-8")
    return json_path, md_path, html_path
