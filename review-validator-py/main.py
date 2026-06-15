"""
main.py -- Multi-Agent Review Validator CLI

Usage:
    python main.py seed             - Load 10 sample reviews
    python main.py list             - Show all reviews in a table
    python main.py add              - Add a new review interactively
    python main.py validate <id>    - Validate one review with all 3 agents
    python main.py validate-all     - Validate all PENDING reviews
    python main.py stats            - Show summary dashboard
    python main.py clear            - Delete all data
"""

import os
import sys
import io
import time

# Force UTF-8 output on Windows to support unicode characters
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import typer
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt, IntPrompt, Confirm
from rich import box
from dotenv import load_dotenv

load_dotenv()

# ── Setup ─────────────────────────────────────────────────────────────────────

app     = typer.Typer(help="Multi-Agent Review Validator -- powered by LangGraph")
console = Console()

VERDICT_COLORS = {
    "APPROVED":     "bold green",
    "HUMAN_REVIEW": "bold yellow",
    "BLOCKED":      "bold red",
    "PENDING":      "dim white",
    "REAL":         "green",
    "GENUINE":      "green",
    "VERIFIED":     "green",
    "SUSPICIOUS":   "yellow",
    "GENERIC":      "yellow",
    "FAKE":         "red",
    "UNVERIFIED":   "red",
}

def _color(verdict: str) -> str:
    return VERDICT_COLORS.get(verdict, "white")

def _badge(verdict: str) -> str:
    icons = {
        "APPROVED":     "[OK]",
        "HUMAN_REVIEW": "[??]",
        "BLOCKED":      "[NO]",
        "PENDING":      "[..]",
        "REAL":         "[OK]",
        "GENUINE":      "[OK]",
        "VERIFIED":     "[OK]",
        "SUSPICIOUS":   "[!!]",
        "GENERIC":      "[!!]",
        "FAKE":         "[XX]",
        "UNVERIFIED":   "[XX]",
    }
    icon = icons.get(verdict, "[ ]")
    color = _color(verdict)
    return f"[{color}]{icon} {verdict}[/{color}]"

def _mode_banner():
    groq_key         = os.getenv("GROQ_API_KEY", "")
    groq_content_key = os.getenv("GROQ_CONTENT_API_KEY", "")

    groq_live         = groq_key         and "xxxxxx" not in groq_key         and groq_key         != "your_groq_api_key_here"
    groq_content_live = groq_content_key and "xxxxxx" not in groq_content_key and groq_content_key != "your_groq_content_api_key_here"

    cred_mode    = "[green]LIVE - Groq LLaMA 3.3[/green]"  if groq_live         else "[yellow]SIMULATED (no API key)[/yellow]"
    content_mode = "[green]LIVE - Groq LLaMA 3.3[/green]"  if groq_content_live else "[yellow]SIMULATED (no API key)[/yellow]"

    console.print(Panel(
        f"  Credibility Agent : {cred_mode}\n"
        f"  Content Agent     : {content_mode}\n"
        f"  Purchase Agent    : [green]LIVE - Rule-based (always on)[/green]",
        title="[bold cyan]Agent Mode[/bold cyan]",
        border_style="cyan",
        expand=False,
    ))


# ── Commands ──────────────────────────────────────────────────────────────────

@app.command()
def seed():
    """Load 10 sample reviews and orders into the local database."""
    from db.store import seed_reviews
    console.print()
    with Progress(SpinnerColumn(), TextColumn("[cyan]Seeding database..."), transient=True) as p:
        p.add_task("")
        seed_reviews()
        time.sleep(0.5)
    console.print("[bold green]  Done! Seeded 10 reviews and 5 orders into data/reviews.json[/bold green]")
    console.print("[dim]  Run [bold]python main.py list[/bold] to see them.[/dim]\n")


@app.command(name="list")
def list_reviews():
    """Display all reviews in a colour-coded table."""
    from db.store import get_all_reviews
    reviews = get_all_reviews()
    console.print()

    if not reviews:
        console.print("[yellow]No reviews found. Run 'python main.py seed' first.[/yellow]\n")
        raise typer.Exit()

    table = Table(
        title=f"[bold cyan]Review Database ({len(reviews)} reviews)[/bold cyan]",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold magenta",
        show_lines=True,
    )
    table.add_column("ID",          style="dim",    width=12)
    table.add_column("Reviewer",    width=18)
    table.add_column("Product",     width=22)
    table.add_column("⭐ Rating",   justify="center", width=8)
    table.add_column("Status",      justify="center", width=14)
    table.add_column("Submitted",   width=12)

    for r in reviews:
        stars  = "⭐" * r.get("starRating", 0)
        status = r.get("status", "PENDING")
        table.add_row(
            r.get("reviewId", ""),
            r.get("reviewerName", ""),
            r.get("productName", "")[:22],
            stars,
            _badge(status),
            str(r.get("submittedAt", ""))[:10],
        )

    console.print(table)
    console.print()


@app.command()
def add():
    """Interactively add a new review to the database."""
    from db.store import add_review
    console.print()
    console.print(Panel("[bold cyan]Add a New Review[/bold cyan]\n"
                        "Fill in the fields below. Press Ctrl+C to cancel.",
                        border_style="cyan"))
    console.print()

    try:
        review = {
            "reviewerName":     Prompt.ask("  Reviewer name"),
            "reviewerEmail":    Prompt.ask("  Reviewer email"),
            "accountCreatedAt": Prompt.ask("  Account created date [dim](YYYY-MM-DD)[/dim]"),
            "totalPastReviews": IntPrompt.ask("  Total past reviews on platform", default=0),
            "reviewsLast24h":   IntPrompt.ask("  Reviews submitted in the last 24 h", default=0),
            "productId":        Prompt.ask("  Product ID [dim](e.g. prod_001)[/dim]"),
            "productName":      Prompt.ask("  Product name"),
            "reviewText":       Prompt.ask("  Review text"),
            "starRating":       IntPrompt.ask("  Star rating [dim](1–5)[/dim]", default=5),
        }

        added = add_review(review)
        console.print()
        console.print(f"[bold green]  Review saved with ID: [white]{added['reviewId']}[/white][/bold green]")
        console.print(f"[dim]  Run: python main.py validate {added['reviewId']}[/dim]\n")
    except (KeyboardInterrupt, typer.Abort):
        console.print("\n[yellow]Cancelled.[/yellow]\n")


@app.command()
def validate(review_id: str = typer.Argument(..., help="The review ID to validate (e.g. rev_001)")):
    """Run all 3 agents on a single review and display the report."""
    from db.store import get_review_by_id, update_review
    from graph.validator_graph import validate_review

    console.print()
    _mode_banner()
    console.print()

    review = get_review_by_id(review_id)
    if not review:
        console.print(f"[red]  Review '{review_id}' not found. Run 'python main.py list' to see IDs.[/red]\n")
        raise typer.Exit(1)

    console.print(Panel(
        f"  [bold]Reviewer:[/bold]  {review['reviewerName']} ([dim]{review['reviewerEmail']}[/dim])\n"
        f"  [bold]Product:[/bold]   {review['productName']}\n"
        f"  [bold]Rating:[/bold]    {'*' * review['starRating']}/5\n"
        f"  [bold]Text:[/bold]      {review['reviewText'][:120]}{'...' if len(review['reviewText']) > 120 else ''}",
        title=f"[bold white]Validating Review: {review_id}[/bold white]",
        border_style="white",
    ))
    console.print()

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Running agents in parallel via LangGraph...[/cyan]"),
        transient=True,
    ) as progress:
        progress.add_task("")
        result = validate_review(review)

    cred     = result.get("cred",     {})
    content  = result.get("content",  {})
    purchase = result.get("purchase", {})
    score    = result.get("score",    0)
    verdict  = result.get("verdict",  "HUMAN_REVIEW")

    # ── Agent breakdown table ──────────────────────────────────────────────
    table = Table(
        title="[bold]Agent Breakdown[/bold]",
        box=box.ROUNDED,
        border_style="dim white",
        header_style="bold white",
        show_lines=True,
        expand=False,
    )
    table.add_column("Agent",   width=22)
    table.add_column("Score",   justify="center", width=8)
    table.add_column("Verdict", justify="center", width=14)
    table.add_column("Reason",  width=52)

    table.add_row(
        "[1] Credibility Agent",
        f"[bold]{cred.get('score', '?')}[/bold]",
        _badge(cred.get("verdict", "?")),
        cred.get("reason", ""),
    )
    table.add_row(
        "[2] Content Agent",
        f"[bold]{content.get('score', '?')}[/bold]",
        _badge(content.get("verdict", "?")),
        content.get("reason", ""),
    )
    table.add_row(
        "[3] Purchase Agent",
        f"[bold]{purchase.get('score', '?')}[/bold]",
        _badge(purchase.get("verdict", "?")),
        purchase.get("reason", ""),
    )

    console.print(table)

    # Content flags
    flags = content.get("flags", [])
    if flags:
        console.print(f"\n  [dim]Content flags: {', '.join(flags)}[/dim]")

    # ── Final verdict panel ────────────────────────────────────────────────
    color = _color(verdict)
    icon  = {"APPROVED": "[OK]", "HUMAN_REVIEW": "[??]", "BLOCKED": "[NO]"}.get(verdict, "[  ]")

    console.print()
    console.print(Panel(
        f"[{color}]  {icon}  VERDICT: {verdict}\n"
        f"      Final Score: {score} / 100\n\n"
        f"  Weights: Credibility x40%  Content x40%  Purchase x20%[/{color}]",
        title="[bold]Final Decision[/bold]",
        border_style=color.replace("bold ", ""),
        expand=False,
    ))
    console.print()

    # Persist result
    update_review(review_id, {
        "status": verdict if verdict in ("APPROVED", "BLOCKED") else "HUMAN_REVIEW",
        "validationResult": {
            "cred":       cred,
            "content":    content,
            "purchase":   purchase,
            "finalScore": score,
            "verdict":    verdict,
        },
    })
    console.print("[dim]  Result saved to data/reviews.json[/dim]\n")


@app.command(name="validate-all")
def validate_all():
    """Validate every PENDING review in the database."""
    from db.store import get_pending_reviews

    console.print()
    _mode_banner()
    console.print()

    pending = get_pending_reviews()
    if not pending:
        console.print("[green]✅  No PENDING reviews to validate.[/green]\n")
        raise typer.Exit()

    console.print(f"[bold cyan]Found {len(pending)} pending review(s). Running agents...[/bold cyan]\n")

    for i, review in enumerate(pending, 1):
        rid = review["reviewId"]
        console.print(f"[bold white][{i}/{len(pending)}] Validating {rid} - {review['reviewerName']}[/bold white]")

        # Reuse the single-review validate logic
        validate(rid)


@app.command()
def stats():
    """Show a summary dashboard of all reviews."""
    from db.store import get_all_reviews

    reviews = get_all_reviews()
    console.print()

    if not reviews:
        console.print("[yellow]No data yet. Run 'python main.py seed' first.[/yellow]\n")
        raise typer.Exit()

    total    = len(reviews)
    by_status: dict[str, int] = {}
    scores   = []

    for r in reviews:
        status = r.get("status", "PENDING")
        by_status[status] = by_status.get(status, 0) + 1
        vr = r.get("validationResult") or {}
        if "finalScore" in vr:
            scores.append(vr["finalScore"])

    avg_score = round(sum(scores) / len(scores)) if scores else "N/A"

    # Summary table
    table = Table(
        title="[bold cyan]Review Dashboard[/bold cyan]",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold magenta",
    )
    table.add_column("Metric",  width=28)
    table.add_column("Value",   justify="right", width=14)

    table.add_row("Total reviews",         f"[bold]{total}[/bold]")
    table.add_row("", "")

    status_order = ["APPROVED", "HUMAN_REVIEW", "BLOCKED", "PENDING"]
    for s in status_order:
        count = by_status.get(s, 0)
        if count:
            table.add_row(f"  {_badge(s)}", f"[bold]{count}[/bold]")

    table.add_row("", "")
    table.add_row("Average validation score", f"[bold]{avg_score}[/bold]")
    table.add_row("Reviews validated",         f"[bold]{len(scores)}[/bold]")

    console.print(table)
    console.print()


@app.command()
def clear():
    """Delete ALL reviews and orders from the database."""
    from db.store import clear_all
    console.print()
    if Confirm.ask("[red]Are you sure you want to delete ALL data?[/red]"):
        clear_all()
        console.print("[bold green]  Database cleared.[/bold green]\n")
    else:
        console.print("[dim]Cancelled.[/dim]\n")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
