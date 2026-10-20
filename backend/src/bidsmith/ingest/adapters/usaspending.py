"""USAspending.gov award search -> Project records. Free API, no key."""

from datetime import date
from typing import Iterator

import httpx

from bidsmith.ingest.classify import classify_building_type, clean_description, title_from_description
from bidsmith.schemas import Project

API = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
FIELDS = [
    "Award ID",
    "Recipient Name",
    "Award Amount",
    "Description",
    "Start Date",
    "End Date",
    "Awarding Agency",
    "Place of Performance State Code",
    "NAICS",
    "PSC",
    "generated_internal_id",
]
CONTRACT_TYPES = ["A", "B", "C", "D"]


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def row_to_project(row: dict, owner_company_id: str) -> Project:
    naics = row.get("NAICS") or {}
    psc = row.get("PSC") or {}
    description = clean_description(row.get("Description"))
    psc_desc = (psc.get("description") or "").lower()
    agency = row.get("Awarding Agency")
    return Project(
        id=f"usa:{row['generated_internal_id']}",
        owner_company_id=owner_company_id,
        source="usaspending",
        title=title_from_description(description) or row.get("Award ID", "Untitled award"),
        client=agency,
        award_value=row.get("Award Amount"),
        start_date=_parse_date(row.get("Start Date")),
        end_date=_parse_date(row.get("End Date")),
        state=row.get("Place of Performance State Code"),
        naics=naics.get("code"),
        psc=psc.get("code"),
        building_type=classify_building_type(description, psc_desc),
        description=f"{description} (PSC: {psc_desc}; agency: {agency}; award {row.get('Award ID')})",
    )


class USAspendingAdapter:
    name = "usaspending"

    def __init__(
        self,
        owner_company_id: str,
        recipient_names: list[str],
        naics: list[str] | None = None,
        start_date: str = "2012-10-01",
        end_date: str | None = None,
        max_records: int = 150,
        min_award: float = 100_000,
        client: httpx.Client | None = None,
    ):
        self.owner_company_id = owner_company_id
        self.recipient_names = recipient_names
        self.naics = naics or []
        self.start_date = start_date
        self.end_date = end_date or date.today().isoformat()
        self.max_records = max_records
        self.min_award = min_award
        self.client = client or httpx.Client(timeout=60)

    def _payload(self, recipient: str, page: int) -> dict:
        filters: dict = {
            "award_type_codes": CONTRACT_TYPES,
            "recipient_search_text": [recipient],
            "time_period": [{"start_date": self.start_date, "end_date": self.end_date}],
        }
        if self.naics:
            filters["naics_codes"] = {"require": self.naics}
        return {
            "filters": filters,
            "fields": FIELDS,
            "limit": 100,
            "page": page,
            "sort": "Award Amount",
            "order": "desc",
        }

    def iter_projects(self) -> Iterator[Project]:
        seen: set[str] = set()
        for recipient in self.recipient_names:
            page = 1
            count = 0
            while count < self.max_records:
                resp = self.client.post(API, json=self._payload(recipient, page))
                resp.raise_for_status()
                body = resp.json()
                for row in body.get("results", []):
                    if (row.get("Award Amount") or 0) < self.min_award:
                        continue
                    project = row_to_project(row, self.owner_company_id)
                    if project.id in seen:
                        continue
                    seen.add(project.id)
                    count += 1
                    yield project
                    if count >= self.max_records:
                        break
                if not body.get("page_metadata", {}).get("hasNext"):
                    break
                page += 1
