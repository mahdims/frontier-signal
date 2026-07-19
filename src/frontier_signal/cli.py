from __future__ import annotations

import json
from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table

from .config import load_sources
from .collectors.manual import load_jsonl
from .db import init_db, mark_report_delivered, prune_pending_items, save_items
from .pipeline import analyze_pending
from .report import render_daily
from .runner import collect_all
from .settings import settings

app = typer.Typer(no_args_is_help=True)
console = Console()


def _prune_backlog(max_age_days: int) -> dict[str, int]:
    sources = load_sources()
    active_source_ids = {
        source.id
        for source in sources
        if source.enabled
    }
    issue_disabled_source_ids = {
        source.id
        for source in sources
        if source.type == "github_repo" and not source.config.get("include_issues", False)
    }
    return prune_pending_items(
        active_source_ids,
        issue_disabled_source_ids,
        max_age_days=max_age_days,
    )


@app.command("init-db")
def init_database():
    init_db()
    console.print("[green]Database initialized.[/green]")


@app.command()
def sources():
    table = Table("ID", "Type", "Enabled", "Region", "Name")
    for s in load_sources():
        table.add_row(s.id, s.type, str(s.enabled), s.region, s.name)
    console.print(table)


@app.command()
def collect(source: str | None = typer.Option(None, help="Only collect one source ID")):
    init_db()
    result = collect_all(source)
    console.print_json(json.dumps(result))


@app.command("ingest-manual")
def ingest_manual(path: Path):
    init_db()
    items = load_jsonl(path)
    inserted, skipped = save_items(items)
    console.print({"inserted": inserted, "skipped": skipped})


@app.command()
def analyze(limit: int = 100):
    init_db()
    successes, failures = analyze_pending(limit)
    console.print({"analyzed": successes, "failed": failures})


@app.command("prune-backlog")
def prune_backlog(days: int = 7):
    """Remove stale or disabled unanalysed items before they incur LLM cost."""
    init_db()
    console.print(_prune_backlog(days))


@app.command()
def report(hours: int = 30, include_reported: bool = False):
    init_db()
    result = render_daily(hours, include_reported=include_reported)
    status = "Reused pending report" if result.reused_pending else "Report written"
    console.print(f"[green]{status}:[/green] {result.path} (id={result.report_id})")


@app.command("mark-report-delivered")
def mark_delivered(report_id: str):
    init_db()
    if not mark_report_delivered(report_id):
        console.print(f"[red]Unknown report ID:[/red] {report_id}")
        raise typer.Exit(code=1)
    console.print(f"[green]Report marked delivered:[/green] {report_id}")


@app.command("run-daily")
def run_daily(include_reported: bool = False):
    init_db()
    collection = collect_all()
    console.print_json(json.dumps(collection))
    console.print({"backlog_cleanup": _prune_backlog(settings.max_item_age_days)})
    successes, failures = analyze_pending()
    console.print({"analyzed": successes, "failed": failures})
    result = render_daily(30, include_reported=include_reported)
    console.print(
        f"[green]Daily run complete:[/green] {result.path} (id={result.report_id})"
    )


if __name__ == "__main__":
    app()
