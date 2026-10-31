"""Pydantic request/response schemas. Structured booking input is the contract the Part-2 Gemini layer will fill."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

DAYS = ("MON", "TUE", "WED", "THU", "FRI")
FEATURES = ("accessible", "computers", "pa_system", "projector", "stage", "ac", "power_benches")
ROOM_TYPES = ("classroom", "lecture_hall", "auditorium", "seminar_hall", "outdoor", "lab_cs", "lab_elec",
              "lab_phy", "workshop", "lab_civil")


class Window(BaseModel):
    day: Literal["MON", "TUE", "WED", "THU", "FRI"]
    from_period: int = Field(ge=1, le=13)
    to_period: int = Field(ge=1, le=13)

    @field_validator("to_period")
    @classmethod
    def _order(cls, v, info):
        if "from_period" in info.data and v < info.data["from_period"]:
            raise ValueError("to_period must be >= from_period")
        return v


class BookingIn(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    attendance: int = Field(ge=1, le=5000)
    duration_periods: int = Field(ge=1, le=13)
    windows: list[Window] = Field(min_length=1)
    room_types: list[str] = Field(min_length=1)
    needs: list[str] = []
    requested_room: str | None = None
    mandatory_for_groups: list[str] = []
    requested_category: Literal["institute_event", "guest_lecture", "department_event", "club_event"] = "club_event"
    department: str | None = None
    raw_text: str = ""

    @field_validator("room_types")
    @classmethod
    def _rt(cls, v):
        bad = [x for x in v if x not in ROOM_TYPES]
        if bad:
            raise ValueError(f"unknown room type(s) {bad}")
        return v

    @field_validator("needs")
    @classmethod
    def _needs(cls, v):
        bad = [x for x in v if x not in FEATURES]
        if bad:
            raise ValueError(f"unknown need(s) {bad}")
        return v


class DecisionIn(BaseModel):
    action: Literal["approve", "reject"]
    reason: str = ""
    # optional human override of the proposed placement (re-validated by the backend)
    room_id: str | None = None
    day: Literal["MON", "TUE", "WED", "THU", "FRI"] | None = None
    start_period: int | None = None


class DisruptionIn(BaseModel):
    changes: list[dict[str, Any]] = Field(min_length=1)
    description: str = ""
    time_limit_s: int = Field(default=90, ge=10, le=270)


class GenerateIn(BaseModel):
    seed: int | None = None
    time_limit_s: int = Field(default=120, ge=10, le=270)
    include_exams: bool = True
    include_bookings: bool = True
    fresh: bool = False


class LoginIn(BaseModel):
    username: str
    password: str
