from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from app.services.daily_planner import run_daily_plans_for_all

_scheduler: BackgroundScheduler | None = None


def start_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    tz = pytz.timezone("Asia/Jerusalem")
    _scheduler = BackgroundScheduler(timezone=tz)
    _scheduler.add_job(
        run_daily_plans_for_all,
        trigger=CronTrigger(hour=7, minute=0, timezone=tz),
        id="daily_plans",
        replace_existing=True,
    )
    _scheduler.start()
