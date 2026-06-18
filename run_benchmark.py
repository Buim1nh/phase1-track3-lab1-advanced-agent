from __future__ import annotations
import json
from pathlib import Path
import typer
from rich import print
from src.reflexion_lab.agents import ReActAgent, ReflexionAgent
from src.reflexion_lab.reporting import build_report, save_report
from src.reflexion_lab.utils import load_dataset, save_jsonl
app = typer.Typer(add_completion=False)

@app.command()
def main(
    dataset: str = "data/hotpot_mini.json",
    out_dir: str = "outputs/sample_run",
    reflexion_attempts: int = 3,
    use_mock: bool = typer.Option(True, "--use-mock/--no-use-mock", help="Run with mock responses or live API calls")
) -> None:
    examples = load_dataset(dataset)
    react = ReActAgent()
    reflexion = ReflexionAgent(max_attempts=reflexion_attempts)
    react_records = [react.run(example, use_mock=use_mock) for example in examples]
    reflexion_records = [reflexion.run(example, use_mock=use_mock) for example in examples]
    all_records = react_records + reflexion_records
    out_path = Path(out_dir)
    save_jsonl(out_path / "react_runs.jsonl", react_records)
    save_jsonl(out_path / "reflexion_runs.jsonl", reflexion_records)
    report = build_report(all_records, dataset_name=Path(dataset).name, mode="mock" if use_mock else "deepseek")
    json_path, md_path, html_path = save_report(report, out_path)
    print(f"[green]Saved[/green] {json_path}")
    print(f"[green]Saved[/green] {md_path}")
    print(f"[green]Saved[/green] {html_path}")
    print(json.dumps(report.summary, indent=2))

if __name__ == "__main__":
    app()
