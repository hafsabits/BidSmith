"""SAM.gov Get Opportunities API -> local file.

Docs: https://open.gsa.gov/api/get-opportunities-public-api/

Two environments, each with its own API key:
  - production: https://api.sam.gov      (key from Account Details on sam.gov)
  - alpha:      https://api-alpha.sam.gov (prod-like test data; key from Account Details on alpha.sam.gov)

Public keys allow only a handful of requests per day, so every fetch runs against a
request budget, results are merged into data/fixtures/sam_live.json, and descriptions
already fetched are never requested again.
"""

import html
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx

from bidsmith.schemas import Opportunity
from bidsmith.settings import get_settings

BASE_URLS = {
    "production": "https://api.sam.gov",
    "alpha": "https://api-alpha.sam.gov",
}
SEARCH_PATH = "/opportunities/v2/search"
DEFAULT_NAICS = ["236220", "236210"]
# o = solicitation, k = combined synopsis/solicitation, p = presolicitation
NOTICE_TYPES = "o,k,p"


class SamApiError(RuntimeError):
    pass


def search_url(env: str) -> str:
    if env not in BASE_URLS:
        raise ValueError(f"SAM_ENV must be one of {sorted(BASE_URLS)}, got '{env}'")
    return BASE_URLS[env] + SEARCH_PATH


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


def _check(resp: httpx.Response) -> dict:
    if resp.status_code == 429:
        raise SamApiError("SAM.gov daily request limit reached (HTTP 429). Try again tomorrow; saved results are kept.")
    # An unrecognized key comes back as 401/403, or as a bare 404 with an empty body (observed on both hosts).
    if resp.status_code in (401, 403) or (resp.status_code == 404 and not resp.content):
        raise SamApiError(
            f"SAM.gov did not accept the API key (HTTP {resp.status_code}). Check that SAM_API_KEY matches SAM_ENV "
            "(alpha keys come from alpha.sam.gov, production keys from sam.gov), and that a newly generated key "
            "has had time to activate."
        )
    if resp.status_code >= 400:
        raise SamApiError(f"SAM.gov error HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def _description_priority(entry: tuple[dict, str | None]) -> tuple:
    item = entry[0]
    deadline = _parse_dt(item.get("responseDeadLine"))
    now = datetime.now(deadline.tzinfo) if deadline and deadline.tzinfo else datetime.now()
    is_open = deadline is not None and deadline > now
    is_solicitation = (item.get("type") or "").lower() in ("solicitation", "combined synopsis/solicitation")
    return (not is_open, not is_solicitation, deadline.timestamp() if deadline else float("inf"))


class _Budget:
    def __init__(self, limit: int):
        self.limit, self.used = limit, 0

    def take(self) -> bool:
        if self.used >= self.limit:
            return False
        self.used += 1
        return True


def fetch_opportunities(
    naics: list[str] | None = None,
    days_back: int = 60,
    per_naics: int = 25,
    max_requests: int | None = None,
    with_descriptions: bool = True,
    out: Path | None = None,
    client: httpx.Client | None = None,
) -> dict:
    """Search SAM.gov and merge results into the live file. Returns a summary dict."""
    settings = get_settings()
    if not settings.sam_api_key:
        raise SamApiError(
            "SAM_API_KEY is not set. Generate one on the Account Details page of "
            f"{'alpha.sam.gov' if settings.sam_env == 'alpha' else 'sam.gov'} and add it to .env."
        )
    url = search_url(settings.sam_env)
    budget = _Budget(max_requests if max_requests is not None else settings.sam_max_requests)
    path = out or settings.sam_live_file
    existing = {o.notice_id: o for o in _read(path)}

    today = date.today()
    params_base = {
        "api_key": settings.sam_api_key,
        "postedFrom": (today - timedelta(days=days_back)).strftime("%m/%d/%Y"),
        "postedTo": today.strftime("%m/%d/%Y"),
        "ptype": NOTICE_TYPES,
        "limit": per_naics,
        "offset": 0,
    }
    found: list[tuple[dict, str | None]] = []
    owns_client = client is None
    client = client or httpx.Client(timeout=60)
    try:
        for code in naics or DEFAULT_NAICS:
            if not budget.take():
                break
            body = _check(client.get(url, params={**params_base, "ncode": code}))
            for item in body.get("opportunitiesData") or []:
                found.append((item, item.get("description")))

        # Spend scarce description requests on open solicitations first, soonest deadline first.
        found.sort(key=_description_priority)
        new = updated = described = 0
        for item, desc_url in found:
            notice_id = item["noticeId"]
            previous = existing.get(notice_id)
            description = previous.description if previous else ""
            if with_descriptions and not description and desc_url and desc_url.startswith("http") and budget.take():
                # Merge, don't replace: the link already carries ?noticeid=...
                d = client.get(httpx.URL(desc_url).copy_merge_params({"api_key": settings.sam_api_key}))
                if d.status_code == 200:
                    description = _strip_html(d.json().get("description", ""))
                    described += 1
                elif d.status_code == 429:
                    budget.used = budget.limit  # stop spending; keep what we have
            opp = to_opportunity(item, description)
            new += previous is None
            updated += previous is not None
            existing[notice_id] = opp
    finally:
        if owns_client:
            client.close()

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([o.model_dump(mode="json") for o in existing.values()], indent=2))
    missing = sum(1 for o in existing.values() if not o.description)
    return {
        "env": settings.sam_env,
        "requests_used": budget.used,
        "new": new,
        "updated": updated,
        "descriptions_fetched": described,
        "missing_descriptions": missing,
        "total_saved": len(existing),
        "file": str(path),
    }


def _read(path: Path) -> list[Opportunity]:
    if not path.exists():
        return []
    return [Opportunity(**o) for o in json.loads(path.read_text())]


def load_opportunities() -> list[Opportunity]:
    """Live SAM.gov results first (if any), then the bundled illustrative samples."""
    settings = get_settings()
    live = _read(settings.sam_live_file)
    samples = _read(settings.sam_fixture) if settings.include_sample_opportunities else []
    seen = {o.notice_id for o in live}
    return live + [o for o in samples if o.notice_id not in seen]


def get_opportunity(notice_id: str) -> Opportunity:
    for o in load_opportunities():
        if o.notice_id == notice_id:
            return o
    raise KeyError(notice_id)
