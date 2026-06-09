from fastapi import APIRouter, HTTPException
from app.services.context import get_user_by_phone, calc_7day_completion_rate, get_tasks_for_plan, get_or_create_today_plan

router = APIRouter()


@router.get("/users/{phone}/stats")
async def user_stats(phone: str):
    user = get_user_by_phone(phone)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    today_plan = get_or_create_today_plan(user.id)
    tasks = get_tasks_for_plan(today_plan.id) if today_plan else []
    rate_7d = calc_7day_completion_rate(user.id)

    return {
        "user": user.to_dict(),
        "streak_days": user.streak_days,
        "completion_rate_7d": rate_7d,
        "today": {
            "plan_date": today_plan.plan_date if today_plan else None,
            "day_type": today_plan.day_type if today_plan else None,
            "completion_rate": today_plan.completion_rate if today_plan else 0,
            "tasks": [t.to_dict() for t in tasks],
        },
    }
