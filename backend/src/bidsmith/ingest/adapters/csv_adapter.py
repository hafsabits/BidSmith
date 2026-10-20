"""CSV export -> Project records. The simplest way for a company to bring its own data."""

import csv
from datetime import date
from pathlib import Path
from typing import Iterator

from bidsmith.ingest.classify import classify_building_type
from bidsmith.schemas import Project


def _num(value: str | None) -> float | None:
    if not value:
        return None
    return float(value.replace(",", "").replace("$", ""))


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


class CSVAdapter:
    """Expected columns: id,title,client,award_value,start_date,end_date,city,state,naics,building_type,description.
    Only `title` is required; missing building_type is inferred from the text."""

    name = "csv"

    def __init__(self, owner_company_id: str, path: str | Path):
        self.owner_company_id = owner_company_id
        self.path = Path(path)

    def iter_projects(self) -> Iterator[Project]:
        with self.path.open(newline="") as f:
            for i, row in enumerate(csv.DictReader(f)):
                description = row.get("description") or ""
                yield Project(
                    id=f"csv:{self.owner_company_id}:{row.get('id') or i}",
                    owner_company_id=self.owner_company_id,
                    source="csv",
                    title=row["title"],
                    client=row.get("client") or None,
                    award_value=_num(row.get("award_value")),
                    start_date=_date(row.get("start_date")),
                    end_date=_date(row.get("end_date")),
                    city=row.get("city") or None,
                    state=row.get("state") or None,
                    naics=row.get("naics") or None,
                    building_type=row.get("building_type") or classify_building_type(row["title"], description),
                    description=description,
                )
