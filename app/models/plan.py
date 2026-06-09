from dataclasses import dataclass, field
from typing import Optional
from app.models.task import Task


@dataclass
class DailyPlan:
    id: str
    user_id: str
    plan_date: str
    day_type: str = "regular"
    morning_message: Optional[str] = None
    completion_rate: float = 0.0
    mood_score: Optional[int] = None
    notes: Optional[str] = None
    tasks: list[Task] = field(default_factory=list)
    created_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "DailyPlan":
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            plan_date=str(data["plan_date"]),
            day_type=data.get("day_type", "regular"),
            morning_message=data.get("morning_message"),
            completion_rate=data.get("completion_rate", 0.0),
            mood_score=data.get("mood_score"),
            notes=data.get("notes"),
            created_at=data.get("created_at"),
        )
