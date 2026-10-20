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
def fetch_sam(days_back: int = 60, per_naics: int = 30):
    """Pull recent opportunities from SAM.gov into data/fixtures (needs SAM_API_KEY)."""
    from bidsmith.ingest.sam import fetch_opportunities

    opps = fetch_opportunities(days_back=days_back, per_naics=per_naics)
    typer.echo(f"Saved {len(opps)} opportunities.")


@app.command()
def run(
    notice_id: str,
    profile: str = typer.Option("ryan"),
    auto_approve: bool = typer.Option(True, help="Accept the bid/no-bid recommendation without prompting"),
):
    """Run the full agent pipeline on one opportunity and print the results."""
    from bidsmith.graph.runner import resume_run, start_run

    thread_id, state = start_run(notice_id, profile, on_update=_print_update)
    fit = state["fit"]
    typer.echo(f"\nRecommendation: {fit.decision.upper()} ({fit.total:.0f}/100)")
    decision = fit.decision
    if not auto_approve:
        decision = typer.prompt("Decision [bid/review/no_bid]", default=fit.decision)
    state = resume_run(thread_id, {"decision": decision, "note": "CLI"}, on_update=_print_update)
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
