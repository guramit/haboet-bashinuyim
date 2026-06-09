import os
import json
from datetime import date
import anthropic
from dotenv import load_dotenv
from app.models.user import User
from app.models.task import Task
from app.models.plan import DailyPlan

load_dotenv()

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def _build_system_prompt(user: User, tasks: list[Task], today_plan: DailyPlan | None, recent_history: str, patterns_summary: str, completion_rate_7d: float) -> str:
    today_str = date.today().strftime("%d/%m/%Y")
    tasks_str = "\n".join(
        f"{t.order_num}. {t.title} – {_status_he(t.status)}"
        for t in tasks
    ) or "אין משימות להיום עדיין."

    return f"""אתה "הבועט בשינויים" – מאמן אישי לבעלי עסקים.
אישיות: חם, תומך, מחבק – אך גם ישיר, מוכוון תוצאות ויודע לדחוף כשצריך.
שפה: עברית תמיד. מקצועי אך לא יבש. אנרגטי אך לא מוגזם.

המשתמש שלך:
- שם: {user.name or "לא ידוע"}
- עסק: {user.business_name or "לא ידוע"} ({user.business_field or "לא ידוע"})
- קשיים עיקריים: {", ".join(user.main_challenges) or "לא צוינו"}
- מחויבות יומית: {user.daily_commitment} דקות
- רצף ימים: {user.streak_days}
- אחוז ביצוע 7 ימים: {int(completion_rate_7d * 100)}%

משימות היום ({today_str}):
{tasks_str}

היסטוריה אחרונה:
{recent_history or "אין היסטוריה עדיין."}

דפוסים מזוהים:
{patterns_summary}

הוראות:
1. זהה את כוונת ההודעה ועדכן סטטוס משימות בהתאם
2. הגב תמיד כמאמן – עם אמפתיה, עידוד, והכוונה
3. אם המשתמש מדלג תדיר – ציין זאת בעדינות
4. החזר JSON בלבד בפורמט הבא (ללא markdown):
{{"message": "...", "actions": [...], "mood_score": N}}

סוגי actions אפשריים:
- {{"type": "update_task", "task_num": N, "status": "completed|skipped|partial"}}
- {{"type": "update_mood", "score": N}}
- {{"type": "add_insight", "text": "..."}}
- {{"type": "add_task", "title": "...", "category": "..."}}"""


def _status_he(status: str) -> str:
    return {
        "pending": "ממתין",
        "completed": "הושלם ✅",
        "skipped": "דולג ⏭",
        "partial": "בוצע חלקית 🔶",
    }.get(status, status)


def chat(user: User, message: str, tasks: list[Task], today_plan: DailyPlan | None,
         recent_history: str, patterns_summary: str, completion_rate_7d: float) -> dict:
    client = _get_client()
    system = _build_system_prompt(user, tasks, today_plan, recent_history, patterns_summary, completion_rate_7d)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": message}],
    )

    raw = response.content[0].text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
        return {"message": raw, "actions": [], "mood_score": None}


def generate_morning_message(user: User, tasks: list[Task], day_type: str) -> str:
    client = _get_client()
    today = date.today()
    days_he = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
    day_name = days_he[today.weekday()]
    date_str = today.strftime("%d/%m/%Y")

    tasks_text = "\n".join(
        f"{i+1}. {t.title}" + (f" (עברה מאתמול)" if t.is_carryover else "")
        for i, t in enumerate(tasks)
    )

    prompt = f"""צור הודעת בוקר ב-WhatsApp בעברית עבור {user.name or "משתמש"}.
יום: {day_name}, {date_str}
סוג יום: {day_type}
משימות:
{tasks_text}

ההודעה צריכה:
- פתיחה אנרגטית ומעוררת
- רשימת המשימות עם אמוג'י מספרים (1️⃣ 2️⃣ 3️⃣)
- טיפ קצר להיום
- סיום עם הוראה: השב "בוצע 1" / "בוצע 2" וכו' לעדכון"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()
