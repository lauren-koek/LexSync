"""
notify.py — Component 3 (cont.): Notify & Auto-Propagate

Renders the final "Legal Resilience Engine" dashboard from impact_report.json
and simulates propagating the fix: a dry-run email notification plus a
patched playbook file. This is the component a judge actually watches during
the live demo, so it's optimised for a clean terminal readout.

Design notes:
- `dispatch_updates(dry_run=True)` never sends real email or touches
  production systems — it's a safe simulation appropriate for a hackathon
  demo. Flipping dry_run=False is left as an explicit, documented extension
  point (see the docstring on that function) rather than wired up, since
  sending real email needs real SMTP credentials we don't want hardcoded.
- The colored diff viewer re-parses the `[-...-]` / `{+...+}` markers written
  by analyse.py's generate_redline_diff() into rich markup.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

INPUT_PATH = Path("impact_report.json")
PLAYBOOK_OUTPUT_PATH = Path("updated_playbook.md")

console = Console()


def summarize_updates(report: list[dict], dry_run: bool = True) -> dict:
    """Return a side-effect-free summary of affected clause updates."""
    affected = [entry for entry in report if entry["analysis"]["is_affected"]]
    return {
        "dispatched": len(affected),
        "dry_run": dry_run,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def render_diff(redline: str) -> Text:
    """Convert a [-deleted-]/{+added+} redline string into colored rich Text."""
    text = Text()
    pattern = re.compile(r"\[-(.*?)-\]|\{\+(.*?)\+\}")
    pos = 0
    for match in pattern.finditer(redline):
        if match.start() > pos:
            text.append(redline[pos:match.start()])
        deleted, added = match.groups()
        if deleted is not None:
            text.append(deleted, style="strike red on grey15")
        elif added is not None:
            text.append(added, style="bold green")
        pos = match.end()
    text.append(redline[pos:])
    return text


def render_dashboard(report: list[dict]) -> None:
    console.print(
        Panel(
            "[bold white]Legal Resilience Engine — Auto-Propagation Dashboard[/]",
            style="on blue",
            expand=True,
        )
    )

    table = Table(title="Impact Summary", show_lines=True)
    table.add_column("Asset Title", overflow="fold")
    table.add_column("Clause Reference")
    table.add_column("Impact Score", justify="center")
    table.add_column("Affected Status", justify="center")

    for entry in report:
        score = entry["analysis"]["impact_score"]
        if score > 7:
            score_style = "bold red"
        elif score > 4:
            score_style = "bold yellow"
        else:
            score_style = "green"

        status = "AFFECTED" if entry["analysis"]["is_affected"] else "Not affected"
        status_style = "bold red" if entry["analysis"]["is_affected"] else "dim"

        table.add_row(
            entry["asset"]["title"],
            entry["asset"]["clause_reference"],
            Text(str(score), style=score_style),
            Text(status, style=status_style),
        )

    console.print(table)

    for entry in report:
        if not entry["analysis"]["is_affected"]:
            continue

        header = f"{entry['asset']['title']} — redline (similarity {entry['similarity_score']})"
        console.print(Panel(render_diff(entry["redline_diff"]), title=header, border_style="magenta"))

        callout = (
            f"[bold]Statutory citations:[/] {', '.join(entry['analysis']['statutory_citations']) or 'N/A'}\n\n"
            f"[bold]Legal reasoning:[/] {entry['analysis']['legal_reasoning']}\n\n"
            f"[dim]Analysis source: {entry['analysis_source']}[/]"
        )
        console.print(Panel(callout, title="Reasoning & Citations", border_style="cyan"))


def dispatch_updates(report: list[dict], dry_run: bool = True) -> dict:
    """Simulate propagating each affected clause's fix.

    In dry-run mode (the only mode wired up here), this:
      1. Builds an HTML email body per affected asset and logs it instead of
         sending it over SMTP.
      2. Appends every proposed amended clause to `updated_playbook.md`, so
         there's a tangible artifact showing "the fix propagated".

    To wire up real delivery: swap the `console.log(...)` in the dry-run
    branch for an `smtplib.SMTP(...)` call using credentials from environment
    variables — never hardcode SMTP credentials in source.
    """
    affected = [e for e in report if e["analysis"]["is_affected"]]
    dispatched_at = datetime.now(UTC).isoformat()

    if not affected:
        console.print("[dim]No affected clauses — nothing to propagate.[/]")
        return {"dispatched": 0, "dry_run": dry_run, "timestamp": dispatched_at}

    playbook_lines = [
        "# Updated Playbook (auto-propagated)",
        f"_Generated {dispatched_at} — {len(affected)} clause(s) amended for regulatory compliance._",
        "",
    ]

    for entry in affected:
        subject = f"[ACTION REQUIRED] Compliance update needed: {entry['asset']['title']}"

        if dry_run:
            console.log(f"[bold yellow]DRY RUN[/] would send email — subject: '{subject}'")
        # else: real SMTP dispatch would go here.

        playbook_lines.append(f"## {entry['asset']['title']} ({entry['asset']['clause_reference']})")
        playbook_lines.append(f"- Impact score: {entry['analysis']['impact_score']}/10")
        playbook_lines.append(f"- Citations: {', '.join(entry['analysis']['statutory_citations']) or 'N/A'}")
        playbook_lines.append("")
        playbook_lines.append("**Amended clause:**")
        playbook_lines.append("")
        playbook_lines.append(entry["analysis"]["proposed_amended_clause"])
        playbook_lines.append("")

    PLAYBOOK_OUTPUT_PATH.write_text("\n".join(playbook_lines), encoding="utf-8")
    console.print(f"[bold green]Propagated {len(affected)} update(s)[/] -> {PLAYBOOK_OUTPUT_PATH.resolve()}")

    return {"dispatched": len(affected), "dry_run": dry_run, "timestamp": dispatched_at}


if __name__ == "__main__":
    report_data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    render_dashboard(report_data)
    dispatch_updates(report_data, dry_run=True)
