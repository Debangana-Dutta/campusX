import csv
import hashlib
import json
import zipfile
from collections import Counter

import pytest

from app.services.dataset.loader import REFERENCE_COUNTS, check_integrity, load_raw
from app.state import AppState
from conftest import ROOT, STARTER


def test_json_parses_and_counts_match_problem_statement(raw):
    rep = check_integrity(raw)
    assert rep.ok, rep.errors
    assert rep.counts == REFERENCE_COUNTS
    assert rep.teaching_hours == 243
    assert rep.count_mismatches == []


@pytest.mark.parametrize("key", ["rooms", "faculty", "student_groups", "courses", "sessions", "booking_requests", "exams"])
def test_unique_ids(raw, key):
    ids = [r["id"] for r in raw[key]]
    assert len(ids) == len(set(ids))


def test_foreign_keys(ds):
    for s in ds.sessions.values():
        assert s["course_id"] in ds.courses and s["faculty_id"] in ds.faculty
        assert all(g in ds.groups for g in s["groups"])
    for e in ds.exams.values():
        assert all(g in ds.groups for g in e["groups"])
    assert ds.cancelled <= set(ds.requests)


def test_csv_files_agree_with_json(raw):
    for key in ("rooms", "faculty", "student_groups", "courses", "sessions", "booking_requests", "exams"):
        rows = list(csv.DictReader(open(STARTER / "data" / "csv" / f"{key}.csv", encoding="utf-8", newline="")))
        assert {r["id"] for r in rows} == {r["id"] for r in raw[key]}, key


def test_known_data_quirks_are_reported_not_hidden(raw):
    rep = check_integrity(raw)
    assert any("LHC-5" in w for w in rep.warnings)          # BR-14 names a room that does not exist
    assert any("BR-17" in w for w in rep.warnings)          # window beyond P13


def test_integrity_rejects_broken_dataset(raw):
    bad = json.loads(json.dumps(raw))
    bad["sessions"][0]["faculty_id"] = "NOPE"
    bad["sessions"].append(dict(bad["sessions"][1]))        # duplicate id
    rep = check_integrity(bad)
    assert not rep.ok
    assert any("NOPE" in e for e in rep.errors) and any("duplicate id" in e for e in rep.errors)


def test_missing_field_detected(raw):
    bad = json.loads(json.dumps(raw))
    del bad["rooms"][0]["capacity"]
    assert not check_integrity(bad).ok


def test_original_source_preserved_byte_for_byte():
    z = ROOT / "source_files" / "CrunchWeek_StarterPack__1_.zip"
    assert z.exists()
    with zipfile.ZipFile(z) as zf:
        for name in ("CrunchWeek_StarterPack/data/cit_public.json", "CrunchWeek_StarterPack/validator.py"):
            extracted = (ROOT / "source_files" / "extracted" / name).read_bytes()
            assert hashlib.sha256(zf.read(name)).hexdigest() == hashlib.sha256(extracted).hexdigest()


def test_repeated_import_is_idempotent():
    st = AppState()
    a = st.import_dataset(reset=True)
    n1 = len(st.live_raw["sessions"])
    b = st.import_dataset()
    c = st.import_dataset()
    assert a.ok and b.ok and c.ok
    assert len(st.live_raw["sessions"]) == n1 == 189        # no duplicated records
