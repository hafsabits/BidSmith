"""The only way agents read the knowledge base.

Ownership rule: `search_past_performance` returns only the active company's records
(what it may claim in a proposal); `search_market_comps` returns only other companies'
records (market intelligence, never cited as the company's own work).
"""

from collections import Counter

from sqlalchemy import Select, func, select

from bidsmith.db.models import ProjectRow
from bidsmith.db.session import get_session
from bidsmith.embeddings import embed_one
from bidsmith.schemas import Project, ProjectHit


def _row_to_project(row: ProjectRow) -> Project:
    return Project(
        id=row.id,
        owner_company_id=row.owner_company_id,
        source=row.source,
        title=row.title,
        client=row.client,
        award_value=row.award_value,
        start_date=row.start_date,
        end_date=row.end_date,
        city=row.city,
        state=row.state,
        naics=row.naics,
        psc=row.psc,
        building_type=row.building_type,
        description=row.description,
    )


def past_performance_query(company_id: str, vector: list[float], k: int) -> Select:
    distance = ProjectRow.embedding.cosine_distance(vector)
    return (
        select(ProjectRow, distance.label("distance"))
        .where(ProjectRow.owner_company_id == company_id)
        .order_by(distance)
        .limit(k)
    )


def market_comps_query(company_id: str, vector: list[float], k: int) -> Select:
    distance = ProjectRow.embedding.cosine_distance(vector)
    return (
        select(ProjectRow, distance.label("distance"))
        .where(ProjectRow.owner_company_id != company_id)
        .order_by(distance)
        .limit(k)
    )


def _run(stmt: Select) -> list[ProjectHit]:
    with get_session() as session:
        rows = session.execute(stmt).all()
    return [ProjectHit(**_row_to_project(r[0]).model_dump(), similarity=round(1 - r[1], 4)) for r in rows]


def search_past_performance(company_id: str, query: str, k: int = 8) -> list[ProjectHit]:
    return _run(past_performance_query(company_id, embed_one(query), k))


def search_market_comps(company_id: str, query: str, k: int = 10) -> list[ProjectHit]:
    return _run(market_comps_query(company_id, embed_one(query), k))


def list_projects(owner: str | None = None, query: str | None = None, limit: int = 50) -> list[Project]:
    if query:
        distance = ProjectRow.embedding.cosine_distance(embed_one(query))
        stmt = select(ProjectRow, distance.label("distance")).order_by(distance)
        if owner:
            stmt = stmt.where(ProjectRow.owner_company_id == owner)
        return _run(stmt.limit(limit))
    stmt = select(ProjectRow).order_by(ProjectRow.award_value.desc().nulls_last()).limit(limit)
    if owner:
        stmt = stmt.where(ProjectRow.owner_company_id == owner)
    with get_session() as session:
        return [_row_to_project(r) for r in session.scalars(stmt).all()]


def company_stats(company_id: str) -> dict:
    """Aggregate facts about a company's record, computed in code for the fit agent."""
    with get_session() as session:
        rows = session.scalars(select(ProjectRow).where(ProjectRow.owner_company_id == company_id)).all()
    values = sorted(r.award_value for r in rows if r.award_value)
    return {
        "project_count": len(rows),
        "by_building_type": dict(Counter(r.building_type for r in rows).most_common()),
        "by_state": dict(Counter(r.state for r in rows if r.state).most_common()),
        "largest_award": values[-1] if values else None,
        "median_award": values[len(values) // 2] if values else None,
    }


def owner_counts() -> dict[str, int]:
    with get_session() as session:
        rows = session.execute(
            select(ProjectRow.owner_company_id, func.count()).group_by(ProjectRow.owner_company_id)
        ).all()
    return {owner: count for owner, count in rows}
