from pathlib import Path

import yaml

from bidsmith.schemas import CompanyProfile
from bidsmith.settings import get_settings

DEFAULT_WEIGHTS = {
    "capability": 0.20,
    "past_performance": 0.20,
    "geography": 0.10,
    "size_vs_bonding": 0.15,
    "set_aside_eligibility": 0.10,
    "competition": 0.10,
    "schedule": 0.15,
}


def load_profile(profile_id: str, profiles_dir: Path | None = None) -> CompanyProfile:
    path = (profiles_dir or get_settings().profiles_dir) / f"{profile_id}.yaml"
    if not path.exists():
        raise KeyError(f"Unknown profile '{profile_id}' (looked for {path})")
    data = yaml.safe_load(path.read_text())
    data.setdefault("id", profile_id)
    data["weights"] = {**DEFAULT_WEIGHTS, **(data.get("weights") or {})}
    return CompanyProfile(**data)


def list_profiles(profiles_dir: Path | None = None) -> list[CompanyProfile]:
    directory = profiles_dir or get_settings().profiles_dir
    return [load_profile(p.stem, directory) for p in sorted(directory.glob("*.yaml"))]
