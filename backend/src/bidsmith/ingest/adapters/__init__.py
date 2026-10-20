from bidsmith.ingest.adapters.base import KnowledgeSource
from bidsmith.ingest.adapters.csv_adapter import CSVAdapter
from bidsmith.ingest.adapters.usaspending import USAspendingAdapter
from bidsmith.schemas import CompanyProfile
from bidsmith.settings import REPO_ROOT


def build_source(profile: CompanyProfile, config: dict) -> KnowledgeSource:
    """Turn one entry of a profile's `sources:` list into an adapter."""
    kind = config["type"]
    if kind == "usaspending":
        return USAspendingAdapter(
            owner_company_id=profile.id,
            recipient_names=config.get("recipient_names") or profile.recipient_names,
            naics=config.get("naics"),
            max_records=config.get("max_records", 150),
        )
    if kind == "csv":
        return CSVAdapter(owner_company_id=profile.id, path=REPO_ROOT / config["path"])
    raise ValueError(f"Unknown knowledge source type: {kind}")


__all__ = ["KnowledgeSource", "CSVAdapter", "USAspendingAdapter", "build_source"]
