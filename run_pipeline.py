"""
run_pipeline.py — Orchestrator

Runs the full Legal Resilience Engine end to end: ingest -> store -> analyse
-> notify. This is the single command for the CLI demo / video recording.

python run_pipeline.py
"""

from __future__ import annotations

from rich.console import Console

import ingest
import store
import analyse
import notify

console = Console()


def main() -> None:
    console.rule("[bold]1. Ingest[/]")
    chunks = ingest.run_ingestion()
    console.print(f"Ingested {len(chunks)} clauses.\n")

    console.rule("[bold]2. Store & Match[/]")
    pairs = store.run_matching()
    console.print(f"Matched {len(pairs)} regulation/asset pair(s).\n")

    console.rule("[bold]3. Analyse[/]")
    report = analyse.run_analysis()
    console.print(f"Analysed {len(report)} pair(s).\n")

    console.rule("[bold]4. Notify[/]")
    notify.render_dashboard(report)
    notify.dispatch_updates(report, dry_run=True)


if __name__ == "__main__":
    main()
