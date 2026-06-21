from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class User:
    id: str
    phone: str
    name: Optional[str] = None
    business_name: Optional[str] = None
    business_field: Optional[str] = None
    main_challenges: list[str] = field(default_factory=list)
    focus_areas: list[str] = field(default_factory=list)
    gender: Optional[str] = None  # "male" | "female" | None
    timezone: str = "Asia/Jerusalem"
    is_active: bool = True
    streak_days: int = 0
    onboarding_step: str = "name"
    paused_at: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "phone": self.phone,
            "name": self.name,
            "business_name": self.business_name,
            "business_field": self.business_field,
            "main_challenges": self.main_challenges,
            "focus_areas": self.focus_areas,
            "gender": self.gender,
            "timezone": self.timezone,
            "streak_days": self.streak_days,
            "onboarding_step": self.onboarding_step,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        return cls(
            id=data["id"],
            phone=data["phone"],
            name=data.get("name"),
            business_name=data.get("business_name"),
            business_field=data.get("business_field"),
            main_challenges=data.get("main_challenges") or [],
            focus_areas=data.get("focus_areas") or [],
            gender=data.get("gender"),
            timezone=data.get("timezone", "Asia/Jerusalem"),
            is_active=data.get("is_active", True),
            streak_days=data.get("streak_days", 0),
            onboarding_step=data.get("onboarding_step", "name"),
            paused_at=data.get("paused_at"),
            created_at=data.get("created_at"),
        )
