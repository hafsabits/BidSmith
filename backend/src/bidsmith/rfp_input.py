"""Turn what a user types into the landing-page box into an Opportunity.

Accepted: a SAM.gov link, a 32-character SAM notice id, a bundled SAMPLE-### id,
or the pasted text of an RFP. Pasted RFPs are kept in data/user_rfps.json (gitignored).
"""

import hashlib
import json
import re
from datetime import date

from bidsmith.ingest import sam
from bidsmith.schemas import Opportunity
from bidsmith.settings import get_settings

SAM_LINK = re.compile(r"sam\.gov/(?:[\w/-]*?/)?opp/([0-9a-f]{32})", re.IGNORECASE)
NOTICE_ID = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)
SAMPLE_ID = re.compile(r"^SAMPLE-\d{3}$", re.IGNORECASE)
MIN_PASTE_CHARS = 200


class InputError(ValueError):
    """The input can't be used; the message is shown to the user."""


def classify(text: str) -> tuple[str, str]:
    """Return (kind, value) where kind is 'sam_link', 'notice_id', 'sample', or 'text'."""
    stripped = text.strip()
    if match := SAM_LINK.search(stripped):
        if len(stripped) < 300:  # a bare link, not a pasted document that happens to contain one
            return "sam_link", match.group(1).lower()
    if NOTICE_ID.match(stripped):
        return "notice_id", stripped.lower()
    if SAMPLE_ID.match(stripped):
        return "sample", stripped.upper()
    return "text", stripped


def _store_path():
    return get_settings().data_dir / "user_rfps.json"


def _read_store() -> dict:
    path = _store_path()
    return json.loads(path.read_text()) if path.exists() else {}


def get_pasted(notice_id: str) -> Opportunity:
    data = _read_store().get(notice_id)
    if data is None:
        raise KeyError(notice_id)
    return Opportunity(**data)


def save_pasted(text: str) -> Opportunity:
    if len(text) < MIN_PASTE_CHARS:
        raise InputError(
            f"That looks too short to be an RFP ({len(text)} characters). Paste the full solicitation text, "
            "a SAM.gov link, or a notice ID."
        )
    digest = hashlib.sha1(text.encode()).hexdigest()[:10]
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "Pasted RFP")
    opp = Opportunity(
        notice_id=f"PASTE-{digest}",
        title=first_line[:140],
        posted_date=date.today(),
        description=text,
        source="pasted",
    )
    store = _read_store()
    store[opp.notice_id] = opp.model_dump(mode="json")
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, indent=2))
    return opp


def needs_sam(text: str) -> bool:
    """True when resolving this input calls SAM.gov (slow, so it should run in the background)."""
    return classify(text)[0] in ("sam_link", "notice_id")


def resolve(text: str) -> Opportunity:
    """Find or create the Opportunity, fetching a SAM description if it isn't saved yet."""
    if not text or not text.strip():
        raise InputError("Paste RFP text, a SAM.gov link, or a notice ID.")
    kind, value = classify(text)
    if kind == "text":
        return save_pasted(value)
    if kind == "sample":
        try:
            return sam.get_opportunity(value)
        except KeyError:
            raise InputError(f"No sample RFP {value}.")
    try:
        opp = sam.lookup_notice(value)
    except KeyError:
        raise InputError(f"SAM.gov has no notice {value} posted in the last year.")
    if opp.source == "sam" and not opp.description:
        opp = sam.ensure_description(opp.notice_id)
    return opp
