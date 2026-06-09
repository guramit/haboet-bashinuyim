from datetime import date, timedelta
from app.database.supabase import get_db
from app.models.user import User
from app.models.task import Task
from app.models.plan import DailyPlan


def get_user_by_phone(phone: str) -> User | None:
    db = get_db()
    clean = phone.replace("whatsapp:", "")
    res = db.table("users").select("*").eq("phone", clean).single().execute()
    if res.data:
        return User.from_dict(res.data)
    return None


def get_or_create_today_plan(user_id: str) -> DailyPlan | None:
    db = get_db()
    today = date.today().isoformat()
    res = db.table("daily_plans").select("*").eq("user_id", user_id).eq("plan_date", today).single().execute()
    if res.data:
        return DailyPlan.from_dict(res.data)
    return None


def get_tasks_for_plan(plan_id: str) -> list[Task]:
    db = get_db()
    res = db.table("tasks").select("*").eq("daily_plan_id", plan_id).order("order_num").execute()
    return [Task.from_dict(t) for t in (res.data or [])]


def get_recent_interactions(user_id: str, limit: int = 15) -> list[dict]:
    db = get_db()
    res = (
        db.table("interactions")
        .select("role,message,created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return list(reversed(res.data or []))


def get_user_patterns(user_id: str) -> list[dict]:
    db = get_db()
    res = (
        db.table("user_patterns")
        .select("pattern_type,description,detected_at")
        .eq("user_id", user_id)
        .order("detected_at", desc=True)
        .limit(10)
        .execute()
    )
    return res.data or []


def calc_7day_completion_rate(user_id: str) -> float:
    db = get_db()
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    res = (
        db.table("daily_plans")
        .select("completion_rate")
        .eq("user_id", user_id)
        .gte("plan_date", week_ago)
        .execute()
    )
    rates = [r["completion_rate"] for r in (res.data or []) if r["completion_rate"] is not None]
    return round(sum(rates) / len(rates), 2) if rates else 0.0


def format_history(interactions: list[dict]) -> str:
    lines = []
    for msg in interactions:
        role = "משתמש" if msg["role"] == "user" else "מאמן"
        lines.append(f"{role}: {msg['message']}")
    return "\n".join(lines)


def summarize_patterns(patterns: list[dict]) -> str:
    if not patterns:
        return "אין דפוסים מזוהים עדיין."
    return "\n".join(f"- {p['description']}" for p in patterns[:5])


def build_context(phone: str) -> dict | None:
    user = get_user_by_phone(phone)
    if not user:
        return None

    today_plan = get_or_create_today_plan(user.id)
    tasks = get_tasks_for_plan(today_plan.id) if today_plan else []
    history = get_recent_interactions(user.id, limit=15)
    patterns = get_user_patterns(user.id)

    return {
        "user": user,
        "today_plan": today_plan,
        "tasks": tasks,
        "recent_history": format_history(history),
        "patterns_summary": summarize_patterns(patterns),
        "completion_rate_7d": calc_7day_completion_rate(user.id),
    }


def save_interaction(user_id: str, role: str, message: str, intent: str | None = None, sentiment: float | None = None):
    db = get_db()
    db.table("interactions").insert({
        "user_id": user_id,
        "role": role,
        "message": message,
        "intent_detected": intent,
        "sentiment_score": sentiment,
    }).execute()


def update_task_status(task_id: str, status: str, notes: str | None = None, difficulty: int | None = None):
    db = get_db()
    update = {"status": status}
    if notes:
        update["user_notes"] = notes
    if difficulty is not None:
        update["difficulty_actual"] = difficulty
    db.table("tasks").update(update).eq("id", task_id).execute()


def update_plan_mood(plan_id: str, mood_score: int):
    db = get_db()
    db.table("daily_plans").update({"mood_score": mood_score}).eq("id", plan_id).execute()


def recalc_completion_rate(plan_id: str):
    db = get_db()
    res = db.table("tasks").select("status").eq("daily_plan_id", plan_id).execute()
    tasks = res.data or []
    if not tasks:
        return
    done = sum(1 for t in tasks if t["status"] in ("completed", "partial"))
    rate = round(done / len(tasks), 2)
    db.table("daily_plans").update({"completion_rate": rate}).eq("id", plan_id).execute()


def save_pattern(user_id: str, pattern_type: str, description: str):
    db = get_db()
    db.table("user_patterns").insert({
        "user_id": user_id,
        "pattern_type": pattern_type,
        "description": description,
    }).execute()
