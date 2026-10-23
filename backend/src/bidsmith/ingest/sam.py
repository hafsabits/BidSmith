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
# SAM.gov can take minutes to answer (90 s for one description in testing), so allow long reads.
SLOW_TIMEOUT = httpx.Timeout(30, read=300)
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
        description_url=item.get("description") if str(item.get("description", "")).startswith("http") else None,
        source="sam",
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


def _write(path: Path, opps: list[Opportunity]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([o.model_dump(mode="json") for o in opps], indent=2))


def _samples() -> list[Opportunity]:
    settings = get_settings()
    if not settings.include_sample_opportunities:
        return []
    return [o.model_copy(update={"source": "sample"}) for o in _read(settings.sam_fixture)]


def load_opportunities() -> list[Opportunity]:
    """Live SAM.gov results (newest posted first), then the bundled illustrative samples."""
    live = _read(get_settings().sam_live_file)
    seen = {o.notice_id for o in live}
    return sort_recent(live) + [o for o in _samples() if o.notice_id not in seen]


def get_opportunity(notice_id: str) -> Opportunity:
    from bidsmith.rfp_input import get_pasted  # pasted RFPs live in their own store

    for o in load_opportunities():
        if o.notice_id == notice_id:
            return o
    return get_pasted(notice_id)


# ---------------------------------------------------------------------------
# Catalog: browse newest-first, pull an older batch only when the saved list runs out,
# and fetch a description only when someone picks that RFP. Keeps daily requests low.
# ---------------------------------------------------------------------------


def sort_recent(opps: list[Opportunity]) -> list[Opportunity]:
    return sorted(opps, key=lambda o: (o.posted_date is not None, o.posted_date), reverse=True)


def _catalog_meta_path() -> Path:
    settings = get_settings()
    return settings.sam_live_file.with_name(f"sam_catalog_{settings.sam_env}.json")


def _read_meta() -> dict:
    path = _catalog_meta_path()
    return json.loads(path.read_text()) if path.exists() else {}


def _require_key() -> str:
    settings = get_settings()
    if not settings.sam_api_key:
        raise SamApiError(
            "SAM_API_KEY is not set. Generate one on the Account Details page of "
            f"{'alpha.sam.gov' if settings.sam_env == 'alpha' else 'sam.gov'} and add it to .env."
        )
    return settings.sam_api_key


def recent_page(offset: int, limit: int) -> dict:
    live = sort_recent(_read(get_settings().sam_live_file))
    meta = _read_meta()
    total_remote = meta.get("total_records")
    exhausted = total_remote is not None and meta.get("next_offset", 0) >= total_remote
    return {
        "items": live[offset : offset + limit],
        "cached": len(live),
        "has_more_cached": offset + limit < len(live),
        "can_fetch_older": bool(get_settings().sam_api_key) and not exhausted,
    }


def fetch_older_batch(batch: int = 100, naics: str = "236220", days_back: int = 364, client: httpx.Client | None = None) -> dict:
    """One SAM.gov request: the next page of notice summaries (no descriptions)."""
    key = _require_key()
    settings = get_settings()
    meta = _read_meta()
    today = date.today()
    window = meta.get("window") or {
        "postedFrom": (today - timedelta(days=days_back)).strftime("%m/%d/%Y"),
        "postedTo": today.strftime("%m/%d/%Y"),
    }
    offset = meta.get("next_offset", 0)
    params = {"api_key": key, **window, "ncode": naics, "ptype": NOTICE_TYPES, "limit": batch, "offset": offset}
    owns = client is None
    client = client or httpx.Client(timeout=SLOW_TIMEOUT)
    try:
        body = _check(client.get(search_url(settings.sam_env), params=params))
    finally:
        if owns:
            client.close()
    existing = {o.notice_id: o for o in _read(settings.sam_live_file)}
    added = 0
    for item in body.get("opportunitiesData") or []:
        previous = existing.get(item["noticeId"])
        opp = to_opportunity(item, previous.description if previous else "")
        added += previous is None
        existing[opp.notice_id] = opp
    _write(settings.sam_live_file, list(existing.values()))
    returned = len(body.get("opportunitiesData") or [])
    meta = {"window": window, "next_offset": offset + returned, "total_records": body.get("totalRecords", 0), "naics": naics}
    _catalog_meta_path().write_text(json.dumps(meta, indent=2))
    return {"added": added, "returned": returned, **meta}


def ensure_description(notice_id: str, client: httpx.Client | None = None) -> Opportunity:
    """Fetch and save the description for one SAM notice if we don't have it yet (one request)."""
    settings = get_settings()
    live = _read(settings.sam_live_file)
    for i, opp in enumerate(live):
        if opp.notice_id != notice_id:
            continue
        if opp.description or not opp.description_url:
            return opp
        key = _require_key()
        owns = client is None
        client = client or httpx.Client(timeout=SLOW_TIMEOUT)
        try:
            resp = client.get(httpx.URL(opp.description_url).copy_merge_params({"api_key": key}))
            data = _check(resp)
        finally:
            if owns:
                client.close()
        live[i] = opp.model_copy(update={"description": _strip_html(data.get("description", ""))})
        _write(settings.sam_live_file, live)
        return live[i]
    return get_opportunity(notice_id)


def lookup_notice(notice_id: str, client: httpx.Client | None = None) -> Opportunity:
    """Find a notice by id: saved list first, otherwise one SAM.gov search by noticeid."""
    try:
        return get_opportunity(notice_id)
    except KeyError:
        pass
    key = _require_key()
    settings = get_settings()
    today = date.today()
    params = {
        "api_key": key,
        "noticeid": notice_id,
        "postedFrom": (today - timedelta(days=364)).strftime("%m/%d/%Y"),
        "postedTo": today.strftime("%m/%d/%Y"),
        "limit": 1,
    }
    owns = client is None
    client = client or httpx.Client(timeout=SLOW_TIMEOUT)
    try:
        items = _check(client.get(search_url(settings.sam_env), params=params)).get("opportunitiesData") or []
    finally:
        if owns:
            client.close()
    if not items:
        raise KeyError(notice_id)
    opp = to_opportunity(items[0], "")
    _write(settings.sam_live_file, _read(settings.sam_live_file) + [opp])
    return opp
