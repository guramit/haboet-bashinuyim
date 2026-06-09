from fastapi import APIRouter
from app.services.daily_planner import run_daily_plans_for_all

router = APIRouter()


@router.post("/daily-plan/generate")
async def trigger_daily_plans():
    run_daily_plans_for_all()
    return {"status": "done"}
