"""Rule-based building-type tagging. Cheap, deterministic, and good enough for retrieval filters."""

import re

from bidsmith.schemas import BuildingType

# Checked in order: more specific types first.
_RULES: list[tuple[BuildingType, tuple[str, ...]]] = [
    ("data_center", ("data center", "datacenter")),
    ("senior_living", ("nursing home", "community living center", "veterans home", "senior living", "assisted living")),
    ("hospital", ("hospital", "medical center", "inpatient", "surgical", "emergency department")),
    ("medical_office", ("clinic", "outpatient", "cboc", "medical office", "health care center", "healthcare center", "dental")),
    ("laboratory", ("laborator", "research facility", " lab ")),
    ("parking_garage", ("parking garage", "parking structure", "parking deck")),
    ("multifamily", ("family housing", "barracks", "dormitor", "apartment", "multifamily", "housing")),
    ("public_safety", ("fire station", "police", "border station", "port of entry", "detention", "correctional", "prison", "jail")),
    ("education", ("school", "education", "training center", "academy", "classroom", "university", "child development")),
    ("warehouse", ("warehouse", "storage", "distribution center", "logistics")),
    ("manufacturing", ("manufactur", "industrial", "plant ", "production facility", "maintenance hangar", "hangar")),
    ("retail", ("retail", "commissary", "exchange", "store")),
    ("office", ("office", "courthouse", "federal building", "administrative", "conference", "headquarters")),
]


def classify_building_type(*texts: str | None) -> BuildingType:
    blob = " " + " ".join(t for t in texts if t).lower() + " "
    for building_type, keywords in _RULES:
        if any(k in blob for k in keywords):
            return building_type
    return "other"


_NOISE = re.compile(r"(IGF::\w+::IGF|TAS::[^:]*::TAS)", re.IGNORECASE)


def clean_description(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", _NOISE.sub("", text)).strip()


def title_from_description(text: str, max_len: int = 90) -> str:
    title = text.split(". ")[0]
    if len(title) > max_len:
        title = title[:max_len].rsplit(" ", 1)[0] + "…"
    return title.title() if title.isupper() else title
