from sqlalchemy import delete

from bidsmith.db.models import ProjectRow
from bidsmith.db.session import get_session
from bidsmith.embeddings import embed
from bidsmith.ingest.adapters import build_source
from bidsmith.schemas import CompanyProfile, Project


def upsert_projects(projects: list[Project]) -> int:
    if not projects:
        return 0
    vectors = embed([p.embedding_text() for p in projects])
    with get_session() as session:
        for project, vector in zip(projects, vectors):
            session.merge(ProjectRow(**project.model_dump(), embedding=vector))
        session.commit()
    return len(projects)


def ingest_profile(profile: CompanyProfile, replace: bool = True) -> dict[str, int]:
    """Run every source configured on the profile. Returns record counts per source."""
    if replace:
        with get_session() as session:
            session.execute(delete(ProjectRow).where(ProjectRow.owner_company_id == profile.id))
            session.commit()
    counts: dict[str, int] = {}
    for config in profile.sources:
        source = build_source(profile, config)
        projects = list(source.iter_projects())
        counts[source.name] = counts.get(source.name, 0) + upsert_projects(projects)
    return counts
