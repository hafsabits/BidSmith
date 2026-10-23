import json

import typer

app = typer.Typer(help="BidSmith command line", no_args_is_help=True)


@app.command("init-db")
def init_db_cmd():
    """Create the pgvector extension and tables."""
    from bidsmith.db.session import init_db

    init_db()
    typer.echo("Database ready.")


@app.command()
def ingest(profile: str = typer.Option("all", help="Profile id, or 'all'")):
    """Load each profile's knowledge sources into the database."""
    from bidsmith.ingest.pipeline import ingest_profile
    from bidsmith.profiles import list_profiles, load_profile

    profiles = list_profiles() if profile == "all" else [load_profile(profile)]
    for p in profiles:
        counts = ingest_profile(p)
        typer.echo(f"{p.id:<20} {counts}")


@app.command("fetch-sam")
def fetch_sam(
    days_back: int = 60,
    per_naics: int = 25,
    naics: list[str] = typer.Option(None, help="NAICS codes to search (repeatable). Default: 236220, 236210"),
    max_requests: int = typer.Option(None, help="Request budget for this run (default SAM_MAX_REQUESTS)"),
    descriptions: bool = typer.Option(True, help="Also fetch description text (one request per notice)"),
):
    """Pull recent opportunities from SAM.gov (SAM_ENV=production|alpha, needs SAM_API_KEY).

    Safe to re-run: results merge into the saved file and descriptions already fetched are reused,
    so a second run tomorrow fills in what today's request limit cut off."""
    from bidsmith.ingest.sam import SamApiError, fetch_opportunities

    try:
        summary = fetch_opportunities(
            naics=naics or None, days_back=days_back, per_naics=per_naics, max_requests=max_requests, with_descriptions=descriptions
        )
    except SamApiError as exc:
        typer.secho(str(exc), fg="red")
        raise typer.Exit(1)
    typer.echo(json.dumps(summary, indent=2))
    if summary["missing_descriptions"]:
        typer.echo("Some notices have no description yet; run fetch-sam again later to fill them in.")


@app.command()
def run(
    rfp: str = typer.Argument(..., help="SAMPLE-### id, SAM.gov notice id or link, or a path to a .txt file of RFP text"),
    profile: str = typer.Option("ryan"),
    pipeline: str = typer.Option("full", help="full, analyst, fit, estimator, risk, or writer"),
    auto_approve: bool = typer.Option(True, help="Accept the bid/no-bid recommendation without prompting"),
):
    """Run agents on one RFP and print the results."""
    from pathlib import Path

    from bidsmith.graph.runner import resume_run, run_status, start_run
    from bidsmith.rfp_input import resolve

    text = Path(rfp).read_text() if rfp.endswith(".txt") and Path(rfp).exists() else rfp
    thread_id, state = start_run(resolve(text), profile, pipeline, step=False, on_update=_print_update)
    if run_status(thread_id)[0] == "waiting_review":
        fit = state["fit"]
        typer.echo(f"\nRecommendation: {fit.decision.upper()} ({fit.total:.0f}/100)")
        decision = fit.decision
        if not auto_approve:
            decision = typer.prompt("Decision [bid/review/no_bid]", default=fit.decision)
        state = resume_run(thread_id, {"decision": decision, "note": "CLI"}, on_update=_print_update, run_all=True)
    typer.echo(json.dumps(_summary(state), indent=2, default=str))


def _print_update(node: str, _update: dict) -> None:
    typer.echo(f"  ✓ {node}")


def _summary(state: dict) -> dict:
    out = {"decision": state.get("human_decision")}
    if est := state.get("estimate"):
        out["estimate"] = {"class": est.aace_class, "total": round(est.total), "low": round(est.low), "high": round(est.high)}
    if risks := state.get("risks"):
        out["top_risks"] = [r.description for r in sorted(risks, key=lambda r: -r.score)[:3]]
    if draft := state.get("proposal"):
        out["proposal_sections"] = [s.title for s in draft.sections]
    out["usage"] = [u.model_dump() for u in state.get("usage", [])]
    return out


if __name__ == "__main__":
    app()
