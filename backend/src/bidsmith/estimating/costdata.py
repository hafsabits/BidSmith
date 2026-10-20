import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from bidsmith.settings import get_settings

BASE_YEAR = 2025  # cost tables are priced at mid-2025


@dataclass(frozen=True)
class BuildingCost:
    archetype: str
    low: float
    typical: float
    high: float
    typical_sf: int


@dataclass(frozen=True)
class Division:
    code: str
    name: str
    pct: float


@dataclass(frozen=True)
class Premium:
    key: str
    pct: float
    description: str


@dataclass(frozen=True)
class CostData:
    buildings: dict[str, BuildingCost]
    splits: dict[str, list[Division]]
    location: dict[str, float]
    escalation: dict[int, float]
    premiums: dict[str, Premium]


def _rows(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def load_cost_data(directory: Path) -> CostData:
    buildings = {
        r["building_type"]: BuildingCost(r["archetype"], float(r["low"]), float(r["typical"]), float(r["high"]), int(r["typical_sf"]))
        for r in _rows(directory / "building_costs.csv")
    }
    splits: dict[str, list[Division]] = {}
    for r in _rows(directory / "csi_splits.csv"):
        splits.setdefault(r["archetype"], []).append(Division(r["division"], r["name"], float(r["pct"]) / 100))
    location = {r["state"]: float(r["factor"]) for r in _rows(directory / "location_index.csv")}
    escalation = {int(r["year"]): float(r["annual_rate"]) for r in _rows(directory / "escalation.csv")}
    premiums = {r["key"]: Premium(r["key"], float(r["pct"]), r["description"]) for r in _rows(directory / "premiums.csv")}
    return CostData(buildings, splits, location, escalation, premiums)


@lru_cache
def get_cost_data() -> CostData:
    return load_cost_data(get_settings().cost_dir)
