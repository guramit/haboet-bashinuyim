from datetime import date, timedelta
from app.database.supabase import get_db
from app.models.user import User
from app.models.task import Task
from app.models.plan import DailyPlan
from app.services import ai_coach, whatsapp


def get_incomplete_tasks_from_yesterday(user_id: str) -> list[dict]:
    db = get_db()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    plan_res = db.table("daily_plans").select("id").eq("user_id", user_id).eq("plan_date", yesterday).limit(1).execute()
    if not plan_res.data:
        return []
    plan_id = plan_res.data[0]["id"]
    res = db.table("tasks").select("*").eq("daily_plan_id", plan_id).in_("status", ["pending", "partial"]).execute()
    return res.data or []


def determine_day_type(user_id: str, weekday: int) -> str:
    db = get_db()
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    res = db.table("daily_plans").select("completion_rate").eq("user_id", user_id).gte("plan_date", week_ago).execute()
    rates = [r["completion_rate"] for r in (res.data or []) if r["completion_rate"] is not None]
    avg = sum(rates) / len(rates) if rates else 0.5

    if avg >= 0.8:
        return "אתגר"
    elif avg <= 0.4:
        return "קל"
    return "רגיל"


def get_recent_task_ids(user_id: str, days: int = 7) -> list[str]:
    db = get_db()
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    plan_res = db.table("daily_plans").select("id").eq("user_id", user_id).gte("plan_date", cutoff).execute()
    plan_ids = [p["id"] for p in (plan_res.data or [])]
    if not plan_ids:
        return []
    task_res = db.table("tasks").select("title").in_("daily_plan_id", plan_ids).execute()
    return [t["title"] for t in (task_res.data or [])]


def select_tasks_from_library(user: User, exclude_titles: list[str], limit: int = 3) -> list[dict]:
    db = get_db()
    res = db.table("task_library").select("*").execute()
    all_tasks = res.data or []

    focus = set(user.focus_areas or [])
    field = user.business_field or ""

    def score(t: dict) -> int:
        s = 0
        tags = set(t.get("tags") or [])
        fields = set(t.get("business_fields") or [])
        if tags & focus:
            s += 2
        if field and field in fields:
            s += 1
        return s

    candidates = [t for t in all_tasks if t["title"] not in exclude_titles]
    candidates.sort(key=score, reverse=True)
    return candidates[:limit]


def _generate_tasks_with_ai(user: User) -> list[dict]:
    import anthropic, os, json
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": f"""צור 3 משימות עסקיות ממוקדות ומעשיות עבור בעל עסק.
שם: {user.name or "לא ידוע"}
עסק: {user.business_name or "לא ידוע"} בתחום {user.business_field or "כללי"}
אתגרים: {", ".join(user.main_challenges) or "לא צוינו"}
תחומי מיקוד: {", ".join(user.focus_areas) or "כללי"}

דרישות:
- כל משימה ניתנת לביצוע היום
- קצרות וספציפיות (עד 8 מילים)
- מותאמות לעסק ולאתגרים

החזר JSON בלבד: {{"tasks": [{{"title": "...", "category": "..."}}]}}"""}],
    )
    try:
        data = json.loads(resp.content[0].text)
        return data.get("tasks", [])
    except Exception:
        return [
            {"title": "לסקור את יעדי השבוע", "category": "תכנון"},
            {"title": "ליצור קשר עם לקוח אחד", "category": "לקוחות"},
            {"title": "לסדר משימה אחת תקועה", "category": "שגרה"},
        ]


def generate_first_plan_from_text(user: User, user_text: str) -> None:
    import anthropic, os, json
    db = get_db()
    today = date.today().isoformat()

    existing = db.table("daily_plans").select("id").eq("user_id", user.id).eq("plan_date", today).execute()
    if existing.data:
        return

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": f"""בעל עסק כתב מה הוא רוצה להשיג. חלץ מהטקסט עד 3 משימות מעשיות לימים הקרובים.

פרטי המשתמש:
- שם: {user.name or "לא ידוע"}
- עסק: {user.business_name or "לא ידוע"} בתחום {user.business_field or "כללי"}
- אתגרים: {", ".join(user.main_challenges) or "לא צוינו"}

מה כתב: "{user_text}"

דרישות:
- כל משימה קצרה וספציפית (עד 8 מילים)
- מבוססת על מה שהוא כתב, לא על השערות
- ניתנת לביצוע בימים הקרובים

החזר JSON בלבד: {{"tasks": [{{"title": "...", "category": "..."}}]}}"""}],
    )
    try:
        data = json.loads(resp.content[0].text)
        ai_tasks = data.get("tasks", [])
    except Exception:
        ai_tasks = [{"title": user_text[:50], "category": "כללי"}]

    plan_res = db.table("daily_plans").insert({
        "user_id": user.id,
        "plan_date": today,
        "day_type": "רגיל",
    }).execute()
    plan_id = plan_res.data[0]["id"]

    all_tasks = []
    for i, raw in enumerate(ai_tasks[:3], start=1):
        task_res = db.table("tasks").insert({
            "daily_plan_id": plan_id,
            "user_id": user.id,
            "title": raw["title"],
            "category": raw.get("category"),
            "order_num": i,
            "is_carryover": False,
        }).execute()
        all_tasks.append(Task.from_dict(task_res.data[0]))

    morning_msg = ai_coach.generate_morning_message(user, all_tasks, "רגיל")
    db.table("daily_plans").update({"morning_message": morning_msg}).eq("id", plan_id).execute()
    whatsapp.send_message(user.phone, morning_msg)


def generate_first_plan(user: User) -> None:
    db = get_db()
    today = date.today().isoformat()

    existing = db.table("daily_plans").select("id").eq("user_id", user.id).eq("plan_date", today).execute()
    if existing.data:
        return

    ai_tasks = _generate_tasks_with_ai(user)

    plan_res = db.table("daily_plans").insert({
        "user_id": user.id,
        "plan_date": today,
        "day_type": "רגיל",
    }).execute()
    plan_id = plan_res.data[0]["id"]

    all_tasks = []
    for i, raw in enumerate(ai_tasks, start=1):
        task_res = db.table("tasks").insert({
            "daily_plan_id": plan_id,
            "user_id": user.id,
            "title": raw["title"],
            "category": raw.get("category"),
            "order_num": i,
            "is_carryover": False,
        }).execute()
        all_tasks.append(Task.from_dict(task_res.data[0]))

    morning_msg = ai_coach.generate_morning_message(user, all_tasks, "רגיל")
    db.table("daily_plans").update({"morning_message": morning_msg}).eq("id", plan_id).execute()
    whatsapp.send_message(user.phone, morning_msg)


def generate_daily_plan(user: User) -> DailyPlan | None:
    db = get_db()
    today = date.today().isoformat()

    existing = db.table("daily_plans").select("id").eq("user_id", user.id).eq("plan_date", today).execute()
    if existing.data:
        return None

    carryover_raw = get_incomplete_tasks_from_yesterday(user.id)
    day_type = determine_day_type(user.id, date.today().weekday())
    recent_titles = get_recent_task_ids(user.id, days=7)

    slots = max(0, 3 - len(carryover_raw))
    new_tasks_raw = select_tasks_from_library(user, exclude_titles=recent_titles, limit=slots)

    plan_res = db.table("daily_plans").insert({
        "user_id": user.id,
        "plan_date": today,
        "day_type": day_type,
    }).execute()
    plan_data = plan_res.data[0]
    plan_id = plan_data["id"]

    all_tasks: list[Task] = []
    order = 1

    for raw in carryover_raw:
        task_res = db.table("tasks").insert({
            "daily_plan_id": plan_id,
            "user_id": user.id,
            "title": raw["title"],
            "description": raw.get("description"),
            "category": raw.get("category"),
            "order_num": order,
            "is_carryover": True,
        }).execute()
        all_tasks.append(Task.from_dict(task_res.data[0]))
        order += 1

    for raw in new_tasks_raw:
        task_res = db.table("tasks").insert({
            "daily_plan_id": plan_id,
            "user_id": user.id,
            "title": raw["title"],
            "description": raw.get("description"),
            "category": raw.get("category"),
            "order_num": order,
            "is_carryover": False,
        }).execute()
        all_tasks.append(Task.from_dict(task_res.data[0]))
        order += 1

    morning_msg = ai_coach.generate_morning_message(user, all_tasks, day_type)

    db.table("daily_plans").update({"morning_message": morning_msg}).eq("id", plan_id).execute()
    whatsapp.send_message(user.phone, morning_msg)

    plan = DailyPlan.from_dict(plan_data)
    plan.tasks = all_tasks
    plan.morning_message = morning_msg
    return plan


def _get_active_users(include_paused: bool = False) -> list[User]:
    db = get_db()
    query = db.table("users").select("*").eq("is_active", True).eq("onboarding_step", "done")
    if not include_paused:
        query = query.is_("paused_at", "null")
    res = query.execute()
    return [User.from_dict(u) for u in (res.data or [])]


def run_daily_plans_for_all():
    for user in _get_active_users():
        try:
            generate_daily_plan(user)
        except Exception as e:
            print(f"Error generating plan for {user.phone}: {e}")


def run_midday_checkins():
    from app.services import ai_coach, whatsapp
    from app.services.context import get_or_create_today_plan, get_tasks_for_plan

    for user in _get_active_users():
        try:
            plan = get_or_create_today_plan(user.id)
            if not plan:
                continue
            tasks = get_tasks_for_plan(plan.id)
            if not tasks:
                continue
            msg = ai_coach.generate_midday_checkin(user, tasks)
            whatsapp.send_message(user.phone, msg)
        except Exception as e:
            print(f"Error midday checkin for {user.phone}: {e}")


def run_evening_summaries():
    from app.services import ai_coach, whatsapp
    from app.services.context import get_or_create_today_plan, get_tasks_for_plan

    for user in _get_active_users():
        try:
            plan = get_or_create_today_plan(user.id)
            if not plan:
                continue
            tasks = get_tasks_for_plan(plan.id)
            if not tasks:
                continue
            msg = ai_coach.generate_evening_summary(user, tasks, plan.mood_score)
            whatsapp.send_message(user.phone, msg)
        except Exception as e:
            print(f"Error evening summary for {user.phone}: {e}")


def run_engagement_check():
    from datetime import datetime, timezone, timedelta
    from app.services import ai_coach, whatsapp
    import anthropic, os, json

    db = get_db()
    now = datetime.now(timezone.utc)
    one_day_ago = (now - timedelta(hours=24)).isoformat()
    two_days_ago = (now - timedelta(hours=48)).isoformat()

    for user in _get_active_users():
        try:
            # בדוק מתי הייתה ההודעה האחרונה מהמשתמש
            res = db.table("interactions").select("created_at").eq("user_id", user.id).eq("role", "user").order("created_at", desc=True).limit(1).execute()

            if not res.data:
                continue

            last_response = res.data[0]["created_at"]

            # יומיים ללא מענה → עצור ושלח "הכל בסדר?"
            if last_response < two_days_ago:
                paused = db.table("users").select("paused_at").eq("id", user.id).limit(1).execute()
                if not paused.data[0].get("paused_at"):
                    db.table("users").update({"paused_at": now.isoformat()}).eq("id", user.id).execute()
                    whatsapp.send_message(user.phone, f"היי {user.name or ''}, הכל בסדר? לא שמעתי ממך כמה ימים.\nאני כאן כשתחזור.")

            # יום ללא מענה → נגיעה קלה
            elif last_response < one_day_ago:
                client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
                resp = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=100,
                    messages=[{"role": "user", "content": f"כתוב משפט אחד בעברית, חם וקצר, לבעל עסק בשם {user.name or 'חבר'} שלא ענה אתמול. לא להזכיר משימות. רק לגעת בו בעדינות ולגרום לו לענות מילה אחת. ללא אימוג'ים."}],
                )
                whatsapp.send_message(user.phone, resp.content[0].text.strip())

        except Exception as e:
            print(f"Error engagement check for {user.phone}: {e}")


def run_followup_checks():
    from datetime import datetime, timezone
    from app.services import ai_coach, whatsapp
    from app.services.context import get_user_by_phone

    db = get_db()
    now = datetime.now(timezone.utc)

    # שעות שקטות: 21:00-08:00 – לא שולחים
    hour_il = (now.hour + 3) % 24  # UTC+3 לישראל
    if hour_il >= 21 or hour_il < 8:
        return

    res = db.table("tasks").select("*").eq("status", "pending").lte(
        "follow_up_scheduled_at", now.isoformat()
    ).not_.is_("follow_up_scheduled_at", "null").execute()

    for task_data in (res.data or []):
        try:
            user_res = db.table("users").select("*").eq("id", task_data["user_id"]).limit(1).execute()
            if not user_res.data:
                continue
            user = User.from_dict(user_res.data[0])
            count = task_data.get("follow_up_count", 0) + 1

            msg = ai_coach.generate_followup_message(user, task_data["title"], count)
            whatsapp.send_message(user.phone, msg)

            if count >= 2:
                # סיימנו לעקוב – מנקים את השדות אבל המשימה נשארת פתוחה
                db.table("tasks").update({
                    "follow_up_scheduled_at": None,
                    "follow_up_count": 0,
                }).eq("id", task_data["id"]).execute()
            else:
                from datetime import timedelta
                # הודעה שנייה אחרי שעה (לא 30 דקות)
                next_at = (now + timedelta(hours=1)).isoformat()
                db.table("tasks").update({
                    "follow_up_scheduled_at": next_at,
                    "follow_up_count": count,
                }).eq("id", task_data["id"]).execute()

        except Exception as e:
            print(f"Error followup for task {task_data.get('id')}: {e}")


def run_weekly_summaries():
    from datetime import timedelta
    from app.services import ai_coach, whatsapp

    db = get_db()
    for user in _get_active_users():
        try:
            week_ago = (date.today() - timedelta(days=7)).isoformat()
            plans_res = db.table("daily_plans").select("completion_rate,mood_score").eq("user_id", user.id).gte("plan_date", week_ago).execute()
            plans = plans_res.data or []

            tasks_res = db.table("tasks").select("status").eq("user_id", user.id).gte("created_at", week_ago).execute()
            tasks = tasks_res.data or []

            completed = sum(1 for t in tasks if t["status"] == "completed")
            skipped = sum(1 for t in tasks if t["status"] == "skipped")
            rates = [p["completion_rate"] for p in plans if p["completion_rate"] is not None]
            avg = round(sum(rates) / len(rates) * 100) if rates else 0

            stats = {
                "active_days": len(plans),
                "completed": completed,
                "skipped": skipped,
                "avg_completion": avg,
            }

            msg = ai_coach.generate_weekly_summary(user, stats)
            whatsapp.send_message(user.phone, msg)
        except Exception as e:
            print(f"Error weekly summary for {user.phone}: {e}")
