from dataclasses import dataclass
from typing import Optional


@dataclass
class Task:
    id: str
    daily_plan_id: str
    user_id: str
    title: str
    order_num: int
    description: Optional[str] = None
    category: Optional[str] = None
    status: str = "pending"
    difficulty_actual: Optional[int] = None
    user_notes: Optional[str] = None
    is_carryover: bool = False
    created_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "status": self.status,
            "difficulty_actual": self.difficulty_actual,
            "user_notes": self.user_notes,
            "order_num": self.order_num,
            "is_carryover": self.is_carryover,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        return cls(
            id=data["id"],
            daily_plan_id=data["daily_plan_id"],
            user_id=data["user_id"],
            title=data["title"],
            order_num=data.get("order_num", 1),
            description=data.get("description"),
            category=data.get("category"),
            status=data.get("status", "pending"),
            difficulty_actual=data.get("difficulty_actual"),
            user_notes=data.get("user_notes"),
            is_carryover=data.get("is_carryover", False),
            created_at=data.get("created_at"),
        )
