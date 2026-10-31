"""TINY SYNTHETIC datasets for isolated unit tests. Not official data; never mixed with the real dataset."""
import copy

BASE = {
    "dataset_id": "synthetic",
    "institute": "Synthetic",
    "calendar": {
        "days": ["MON", "TUE", "WED", "THU", "FRI"],
        "periods": [{"id": i, "start": f"{7 + i:02d}:00" if i <= 5 else f"{8 + i:02d}:00",
                     "end": f"{8 + i:02d}:00" if i <= 5 else f"{9 + i:02d}:00", "teaching": i <= 9} for i in range(1, 14)],
        "lunch": {"after_period": 5, "start": "13:00", "end": "14:00"},
        "lab_start_periods": [2, 6], "event_only_periods": [10, 11, 12, 13],
        "exam_week": {"days": ["MON", "TUE", "WED", "THU", "FRI", "SAT"],
                      "sessions": [{"id": "AM", "start": "09:30", "end": "11:30"}, {"id": "PM", "start": "14:00", "end": "16:00"}]},
    },
    "priority_order": ["exam", "regular_session", "institute_event", "guest_lecture", "department_event", "club_event"],
    "role_category_cap": {"admin": "institute_event", "faculty": "guest_lecture",
                          "department_coordinator": "department_event", "club": "club_event"},
    "rooms": [
        {"id": "R1", "name": "R1", "building": "B", "type": "classroom", "capacity": 50, "features": ["projector"], "accessible": True, "allowed_uses": ["lecture", "tutorial", "exam", "event"]},
        {"id": "R2", "name": "R2", "building": "B", "type": "classroom", "capacity": 50, "features": ["projector"], "accessible": False, "allowed_uses": ["lecture", "tutorial", "exam", "event"]},
        {"id": "L1", "name": "L1", "building": "B", "type": "lab_cs", "capacity": 50, "features": ["computers"], "accessible": True, "allowed_uses": ["lab", "event"]},
    ],
    "room_unavailability": [],
    "faculty": [
        {"id": "FA", "name": "A", "department": "X", "max_hours_per_day": 2, "needs_accessible": False, "unavailable": [], "preferences": []},
        {"id": "FB", "name": "B", "department": "X", "max_hours_per_day": 4, "needs_accessible": False, "unavailable": [], "preferences": []},
    ],
    "student_groups": [
        {"id": "G1", "name": "G1", "year": 1, "department": "X", "size": 40, "needs_accessible": False},
        {"id": "G2", "name": "G2", "year": 1, "department": "X", "size": 40, "needs_accessible": False},
    ],
    "courses": [{"id": "C1", "title": "C1", "department": "X", "year": 1, "lecture_hours": 2, "tutorial_hours": 0, "lab_blocks": 0}],
    "sessions": [],
    "booking_requests": [], "cancellations": [], "exams": [],
}


def session(sid, faculty="FA", groups=("G1",), kind="lecture", dur=1, size=30, types=("classroom",), acc=False, basket=None, fixed=None):
    return {"id": sid, "course_id": "C1", "kind": kind, "groups": list(groups), "faculty_id": faculty, "size": size,
            "duration": dur, "room_types": list(types), "needs_accessible": acc, "basket_slot": basket, "fixed_slot": fixed}


def make(sessions=(), **over):
    d = copy.deepcopy(BASE)
    d["sessions"] = list(sessions)
    d.update(over)
    return d
