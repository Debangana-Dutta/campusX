"""Shared fixtures. Integration tests use the REAL official dataset and the app's own exports.
Synthetic datasets (tests/synthetic.py) are only for isolated unit tests and are clearly separate."""
import json
import os
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_tmp = tempfile.mkdtemp(prefix="campusx_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["STATE_DIR"] = _tmp                      # never touch the developer's real state
os.environ["AUTH_MODE"] = "local"

from app.config import get_settings  # noqa: E402
from app.services.dataset.loader import load_dataset, load_raw  # noqa: E402

STARTER = ROOT / "source_files" / "extracted" / "CrunchWeek_StarterPack"


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture(scope="session")
def raw():
    return load_raw(STARTER / "data" / "cit_public.json")


@pytest.fixture(scope="session")
def ds(raw):
    return load_dataset(STARTER / "data" / "cit_public.json")


@pytest.fixture(scope="session")
def schedule():
    p = ROOT / "exports" / "schedule.json"
    if not p.exists():
        pytest.skip("exports/schedule.json missing: run scripts/generate_exports.py")
    return json.loads(p.read_text())


@pytest.fixture(scope="session")
def schedule_after():
    p = ROOT / "exports" / "schedule_after.json"
    if not p.exists():
        pytest.skip("exports/schedule_after.json missing")
    return json.loads(p.read_text())


@pytest.fixture(scope="session")
def disruption():
    return json.loads((STARTER / "examples" / "sample_disruption.json").read_text())


@pytest.fixture(scope="session")
def base_assign(schedule):
    from app.services.scheduling.solver import from_schedule
    return from_schedule(schedule)
