from typing import Iterator, Protocol

from bidsmith.schemas import Project


class KnowledgeSource(Protocol):
    """Anything that can yield normalized Project records.

    To plug in a company's own data (ERP export, SharePoint, a CRM), implement this
    and register it in `bidsmith.ingest.adapters.build_source`.
    """

    name: str

    def iter_projects(self) -> Iterator[Project]: ...
