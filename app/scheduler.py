from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from app.services.daily_planner import run_daily_plans_for_all, run_midday_checkins, run_evening_summaries, run_weekly_summaries

_scheduler: BackgroundScheduler | None = None


def start_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    tz = pytz.timezone("Asia/Jerusalem")
    _scheduler = BackgroundScheduler(timezone=tz)

    _scheduler.add_job(
        run_daily_plans_for_all,
        trigger=CronTrigger(hour=8, minute=0, timezone=tz),
        id="daily_plans",
        replace_existing=True,
    )

    _scheduler.add_job(
        run_midday_checkins,
        trigger=CronTrigger(hour=13, minute=0, timezone=tz),
        id="midday_checkins",
        replace_existing=True,
    )

    _scheduler.add_job(
        run_evening_summaries,
        trigger=CronTrigger(hour=21, minute=0, timezone=tz),
        id="evening_summaries",
        replace_existing=True,
    )

    # סיכום שבוע – כל שישי ב-17:00
    _scheduler.add_job(
        run_weekly_summaries,
        trigger=CronTrigger(day_of_week="fri", hour=17, minute=0, timezone=tz),
        id="weekly_summaries",
        replace_existing=True,
    )

    _scheduler.start()
