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

אישיות: אתה מדבר כמו חבר שמכיר עסקים לעומק. ישיר, חם, לא מחמיא בחינם.
לא רובוטי. לא מוגזם. לא שולח עשרה אימוג'ים בהודעה.
אתה שואל שאלות טובות, מציין בעיות בעדינות, ודוחף כשצריך.

כלל אימוג'ים: לכל היותר 1-2 אימוג'ים בכל הודעה. לפעמים בכלל בלי.
שפה: עברית תמיד. משפטים קצרים. ענייניים. אנושיים.

גישה למשימות:
- לא כל משימה דורשת ליווי מעמיק. אם משימה פשוטה ("לשלוח מייל", "להתקשר ללקוח") – תזכורת קצרה מספיקה.
- שאל את עצמך: האם המשתמש צריך עזרה לפרק את המשימה, או שהוא פשוט צריך להיזכר לעשות אותה?
- אם נראה פשוט – אל תעמיס. פשוט תזכיר ותאפשר לו ללכת לעשות.

דד-ליינים:
- כשמשתמש מדבר על משימה או מטרה בלי תאריך ברור – עזור לו לקבוע דד-ליין עצמי.
- "כמה שיותר מהר" או "בקרוב" הם לא יעדים. שאל: "עד מתי ספציפית?"
- לאחר שנקבע דד-ליין – חזור עליו בשיחה כנקודת ייחוס.

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
4. אתה מאמן עסקי. אם השיחה יוצאת מתחום העסק והמשימות, ענה בקצרה והחזר את השיחה לעסק בעדינות.
5. החזר JSON בלבד בפורמט הבא (ללא markdown):
{{"message": "...", "actions": [...], "mood_score": N}}

סוגי actions אפשריים:
- {{"type": "update_task", "task_num": N, "status": "completed|skipped|partial"}}
- {{"type": "update_mood", "score": N}}
- {{"type": "add_insight", "text": "..."}}
- {{"type": "add_task", "title": "...", "category": "..."}}
- {{"type": "schedule_followup", "task_num": N}} – השתמש בזה כשהמשתמש אומר שהוא הולך לבצע משימה עכשיו ("אני הולך לעשות", "עכשיו אני מתחיל", "יאללה עושה את זה")"""


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


def generate_followup_message(user: User, task_title: str, followup_count: int) -> str:
    client = _get_client()
    if followup_count == 1:
        prompt = f"""כתוב הודעת מעקב קצרה בעברית עבור {user.name or "משתמש"}, בעל {user.business_name or "עסק"}.
לפני חצי שעה אמר שהולך לבצע: "{task_title}".
עדיין לא עדכן.

כללים:
- התייחס ספציפית למשימה "{task_title}" – לא שאלה גנרית
- משפט אחד בלבד
- טון סקרן, לא שיפוטי
- ללא אימוג'ים"""
    else:
        prompt = f"""כתוב הודעת מעקב שנייה ואחרונה בעברית עבור {user.name or "משתמש"}.
לפני שעה וחצי אמר שהולך לבצע: "{task_title}". עדיין לא עדכן.

כללים:
- התייחס ספציפית למשימה "{task_title}"
- הצע להכניס אותה ללו"ז בהמשך אם לא מתאים עכשיו
- 2 משפטים מקסימום
- טון רגוע ותומך, לא מאשים
- ללא אימוג'ים"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


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

    prompt = f"""כתוב הודעת בוקר בעברית עבור {user.name or "משתמש"}, בעל עסק בתחום {user.business_field or "עסקים"}.
יום: {day_name}, {date_str}
סוג יום: {day_type}
משימות:
{tasks_text}

כללים לכתיבה:
- טון של מאמן אמיתי, לא רובוטי. אנושי, ישיר, תכליתי.
- פתיחה קצרה וחמה – משפט אחד בלבד
- רשימת המשימות ממוספרת (1. 2. 3.) – ללא אימוג'י מספרים
- משפט מוטיבציה קצר ואמיתי, לא קלישאה
- הוראה פשוטה: כתוב "בוצע 1" / "בוצע 2" / "בוצע 3" לעדכון
- לכל היותר אימוג'י אחד בכל ההודעה, ורק אם זה טבעי"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def generate_midday_checkin(user: User, tasks: list[Task]) -> str:
    client = _get_client()
    done = sum(1 for t in tasks if t.status == "completed")
    total = len(tasks)
    tasks_text = "\n".join(f"{t.order_num}. {t.title} – {_status_he(t.status)}" for t in tasks)

    prompt = f"""כתוב הודעת בדיקת צהריים קצרה בעברית עבור {user.name or "משתמש"}.
סטטוס עכשיו: {done}/{total} משימות הושלמו.
משימות:
{tasks_text}

כללים:
- משפט אחד עד שניים בלבד
- אל תמנה את המשימות שוב
- אם הושלמו הרבה – שבח קצר ואמיתי
- אם לא הושלם כלום – שאל בצורה ישירה ולא שיפוטית מה קורה
- טון אנושי, לא רובוטי, לכל היותר אימוג'י אחד"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def generate_evening_summary(user: User, tasks: list[Task], mood_score: int | None) -> str:
    client = _get_client()
    done = sum(1 for t in tasks if t.status == "completed")
    skipped = sum(1 for t in tasks if t.status == "skipped")
    total = len(tasks)
    tasks_text = "\n".join(f"{t.order_num}. {t.title} – {_status_he(t.status)}" for t in tasks)

    prompt = f"""כתוב סיכום יום בעברית עבור {user.name or "משתמש"}, בעל {user.business_name or "עסק"}.
ביצועים היום: {done}/{total} הושלמו, {skipped} דולגו.
משימות:
{tasks_text}
מצב רוח: {mood_score or "לא דווח"}/5

כללים קשיחים:
- 3 משפטים בלבד, לא יותר
- משפט 1: מה היה היום – עובדות בלבד
- משפט 2: משפט חם אחד על הביצועים
- משפט 3: שורה אחת על מחר – לא שאלה, רק הצהרה קצרה ("מחר נמשיך מפה")
- אפס שאלות – בשום אופן לא לשאול כלום
- ללא אימוג'ים
- המשתמש עייף, אל תעמיס עליו"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def generate_weekly_summary(user: User, stats: dict) -> str:
    client = _get_client()

    prompt = f"""כתוב סיכום שבוע בעברית עבור {user.name or "משתמש"}, בעל {user.business_name or "עסק"} בתחום {user.business_field or "עסקים"}.

נתוני השבוע:
- ימים פעילים: {stats.get("active_days", 0)}/7
- משימות שהושלמו: {stats.get("completed", 0)}
- משימות שדולגו: {stats.get("skipped", 0)}
- אחוז ביצוע ממוצע: {stats.get("avg_completion", 0)}%
- רצף נוכחי: {user.streak_days} ימים

כללים:
- 4-5 משפטים בלבד
- נקודה חזקה אחת מהשבוע
- נקודה אחת לשיפור לשבוע הבא – ספציפית, לא כללית
- שאלה אחת לסיום שתעזור לתכנן את השבוע הבא
- טון ישיר ואנושי, לא נאום מוטיבציה
- ללא אימוג'ים"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()
