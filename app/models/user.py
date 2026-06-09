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
    daily_commitment: int = 30
    timezone: str = "Asia/Jerusalem"
    is_active: bool = True
    streak_days: int = 0
    onboarding_step: str = "name"
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
            "daily_commitment": self.daily_commitment,
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
            daily_commitment=data.get("daily_commitment", 30),
            timezone=data.get("timezone", "Asia/Jerusalem"),
            is_active=data.get("is_active", True),
            streak_days=data.get("streak_days", 0),
            onboarding_step=data.get("onboarding_step", "name"),
            created_at=data.get("created_at"),
        )
