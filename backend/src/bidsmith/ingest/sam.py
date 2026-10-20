"""SAM.gov Get Opportunities API -> local fixture.

The public API is rate limited, so we pull once and the app reads the saved file.
Requires a free API key from a SAM.gov account (set SAM_API_KEY in .env).
"""

import html
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx

from bidsmith.schemas import Opportunity
from bidsmith.settings import get_settings

API = "https://api.sam.gov/opportunities/v2/search"
DEFAULT_NAICS = ["236220", "236210"]
# o = solicitation, k = combined synopsis/solicitation, p = presolicitation
NOTICE_TYPES = "o,k,p"


def _strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>|</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", html.unescape(text)).strip()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def to_opportunity(item: dict, description: str) -> Opportunity:
    pop = item.get("placeOfPerformance") or {}
    return Opportunity(
        notice_id=item["noticeId"],
        title=item.get("title") or "Untitled",
        solicitation_number=item.get("solicitationNumber"),
        agency=item.get("fullParentPathName"),
        notice_type=item.get("type"),
        posted_date=date.fromisoformat(item["postedDate"][:10]) if item.get("postedDate") else None,
        response_deadline=_parse_dt(item.get("responseDeadLine")),
        naics=item.get("naicsCode"),
        psc=item.get("classificationCode"),
        set_aside=item.get("typeOfSetAsideDescription") or item.get("typeOfSetAside"),
        place_city=((pop.get("city") or {}).get("name")),
        place_state=((pop.get("state") or {}).get("code")),
        description=description,
        url=item.get("uiLink"),
    )


def fetch_opportunities(
    naics: list[str] | None = None, days_back: int = 60, per_naics: int = 30, out: Path | None = None
) -> list[Opportunity]:
    settings = get_settings()
    if not settings.sam_api_key:
        raise RuntimeError("SAM_API_KEY is not set. Get a free key from your SAM.gov account settings.")
    today = date.today()
    params_base = {
        "api_key": settings.sam_api_key,
        "postedFrom": (today - timedelta(days=days_back)).strftime("%m/%d/%Y"),
        "postedTo": today.strftime("%m/%d/%Y"),
        "ptype": NOTICE_TYPES,
        "limit": per_naics,
    }
    opportunities: list[Opportunity] = []
    with httpx.Client(timeout=60) as client:
        for code in naics or DEFAULT_NAICS:
            resp = client.get(API, params={**params_base, "ncode": code})
            resp.raise_for_status()
            for item in resp.json().get("opportunitiesData", []):
                description = ""
                desc_url = item.get("description")
                if desc_url and desc_url.startswith("http"):
                    d = client.get(desc_url, params={"api_key": settings.sam_api_key})
                    if d.status_code == 200:
                        description = _strip_html(d.json().get("description", ""))
                opportunities.append(to_opportunity(item, description))
    path = out or settings.sam_fixture
    path.write_text(json.dumps([o.model_dump(mode="json") for o in opportunities], indent=2))
    return opportunities


def load_opportunities(path: Path | None = None) -> list[Opportunity]:
    path = path or get_settings().sam_fixture
    if not path.exists():
        return []
    return [Opportunity(**o) for o in json.loads(path.read_text())]


def get_opportunity(notice_id: str) -> Opportunity:
    for o in load_opportunities():
        if o.notice_id == notice_id:
            return o
    raise KeyError(notice_id)
