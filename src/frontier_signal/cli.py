from __future__ import annotations

import json
from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table

from .config import load_sources
from .collectors.manual import load_jsonl
from .db import init_db, save_items
from .pipeline import analyze_pending
from .report import render_daily
from .runner import collect_all

app = typer.Typer(no_args_is_help=True)
console = Console()


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


@app.command()
def report(hours: int = 30):
    init_db()
    path = render_daily(hours)
    console.print(f"[green]Report written:[/green] {path}")


@app.command("run-daily")
def run_daily():
    init_db()
    collection = collect_all()
    console.print_json(json.dumps(collection))
    successes, failures = analyze_pending()
    console.print({"analyzed": successes, "failed": failures})
    path = render_daily(30)
    console.print(f"[green]Daily run complete:[/green] {path}")


if __name__ == "__main__":
    app()
