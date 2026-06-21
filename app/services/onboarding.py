import anthropic
import os
import json
from app.database.supabase import get_db
from app.models.user import User
from app.services import whatsapp, daily_planner

STEPS = ["name", "business_name", "business_field", "challenges", "gender", "focus", "first_plan", "confirm_plan", "done"]

FOCUS_OPTIONS = ["מכירות", "שיווק", "ניהול כספי", "ניהול זמן", "שגרה", "לקוחות", "צוות"]


def start_onboarding(phone: str) -> str:
    db = get_db()
    clean = phone.replace("whatsapp:", "")
    db.table("users").insert({"phone": clean, "onboarding_step": "name"}).execute()
    return (
        "שלום, ברוך הבא לבועט בישבנים.\n\n"
        "אני עוזר עסקי. כל בוקר אשלח לך 3 משימות ממוקדות לעסק, "
        "אעקוב אחרי הביצוע שלך במהלך היום, ואהיה זמין לשיחה חופשית בכל עת.\n\n"
        "מה אני יכול לעשות:\n"
        "— תוכנית עבודה יומית מותאמת אישית\n"
        "— מעקב ועידוד לאורך היום\n"
        "— שיחה על אתגרים עסקיים ופתרונות\n"
        "— סיכום יום ושבוע\n\n"
        "מה אני לא יכול לעשות:\n"
        "— לגשת לאינטרנט או לקבצים שלך\n"
        "— לשלוח מיילים או להפעיל מערכות חיצוניות\n"
        "— לזכור שיחות מעבר ל-15 ההודעות האחרונות\n\n"
        "נתחיל?\n\n*מה שמך?*"
    )


def handle_onboarding(user: User, message: str) -> str:
    db = get_db()
    step = user.onboarding_step
    clean_phone = user.phone

    if step == "name":
        name = message.strip()
        db.table("users").update({"name": name, "onboarding_step": "business_name"}).eq("phone", clean_phone).execute()
        return f"נעים מאוד, {name}!\n\n*האם לעסק שלך יש שם או מותג נפרד מהשם שלך?*\n(אם כן – כתוב אותו. אם לא – כתוב 'לא')"

    elif step == "business_name":
        msg = message.strip()
        biz_name = user.name if msg.lower() in ["לא", "no", "-", "אין"] else msg
        db.table("users").update({"business_name": biz_name, "onboarding_step": "business_field"}).eq("phone", clean_phone).execute()
        return f"*{biz_name}* – *באיזה תחום פועל העסק?*\n(לדוגמה: קמעונאות, שירותים, טכנולוגיה, בריאות, אוכל...)"

    elif step == "business_field":
        db.table("users").update({"business_field": message.strip(), "onboarding_step": "challenges"}).eq("phone", clean_phone).execute()
        return "*מה האתגרים העיקריים שאתה מתמודד איתם בעסק?*\n\n(כתוב בחופשיות – לדוגמה: מציאת לקוחות, ניהול זמן, שיווק, תזרים מזומנים...)"

    elif step == "challenges":
        try:
            client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                messages=[{"role": "user", "content": f"חלץ רשימת אתגרים עיקריים מהטקסט הבא. החזר JSON בלבד: {{\"challenges\": [\"...\", \"...\"]}}\n\nטקסט: {message}"}],
            )
            data = json.loads(resp.content[0].text)
            challenges = data.get("challenges", [message.strip()])
        except Exception:
            challenges = [message.strip()]

        db.table("users").update({"main_challenges": challenges, "onboarding_step": "gender"}).eq("phone", clean_phone).execute()
        return "שאלה אחת לפני שמתחילים –\n*איך לפנות אליך? זכר או נקבה?*"

    elif step == "gender":
        msg = message.strip().lower()
        gender = "female" if any(w in msg for w in ["נקבה", "אישה", "בת", "female"]) else "male"
        db.table("users").update({"gender": gender, "onboarding_step": "focus"}).eq("phone", clean_phone).execute()
        options = "\n".join(f"• {f}" for f in FOCUS_OPTIONS)
        return f"*באילו תחומים תרצה להתמקד?*\n\n{options}\n\n(כתוב את התחומים שבחרת, מופרדים בפסיקה)"

    elif step == "focus":
        chosen = [f.strip() for f in message.replace("،", ",").split(",") if f.strip()]
        if not chosen:
            chosen = ["מכירות"]
        db.table("users").update({"focus_areas": chosen, "onboarding_step": "first_plan"}).eq("phone", clean_phone).execute()

        updated_res = db.table("users").select("*").eq("phone", clean_phone).limit(1).execute()
        updated_user = User.from_dict(updated_res.data[0])
        name = updated_user.name or ""
        return (
            f"מושלם {name}, הפרופיל שלך מוכן!\n\n"
            "בוא נתחיל מיד –\n"
            "*מה אתה רוצה להשיג בימים הקרובים? מה עומד לך על הראש עכשיו?*\n\n"
            "(כתוב בחופשיות – אני אעזור לך להפוך את זה למשימות)"
        )

    elif step == "first_plan":
        updated_res = db.table("users").select("*").eq("phone", clean_phone).limit(1).execute()
        updated_user = User.from_dict(updated_res.data[0])

        tasks = daily_planner.extract_tasks_from_text(updated_user, message)
        tasks_json = json.dumps(tasks, ensure_ascii=False)
        db.table("user_patterns").insert({
            "user_id": updated_user.id,
            "pattern_type": "pending_first_tasks",
            "text": tasks_json,
        }).execute()
        db.table("users").update({"onboarding_step": "confirm_plan"}).eq("phone", clean_phone).execute()

        tasks_text = "\n".join(f"{i+1}. {t['title']}" for i, t in enumerate(tasks))
        return f"הנה מה שחילצתי:\n\n{tasks_text}\n\n*זה נראה נכון? כתוב 'כן' ונתחיל, או תאמר לי מה לשנות.*"

    elif step == "confirm_plan":
        updated_res = db.table("users").select("*").eq("phone", clean_phone).limit(1).execute()
        updated_user = User.from_dict(updated_res.data[0])

        msg_lower = message.strip().lower()
        confirmed = any(w in msg_lower for w in ["כן", "yes", "אוקי", "בסדר", "יופי", "מעולה", "נכון", "סבבה", "ok"])

        pending_res = db.table("user_patterns").select("text").eq("user_id", updated_user.id).eq("pattern_type", "pending_first_tasks").order("created_at", desc=True).limit(1).execute()
        saved_tasks = []
        if pending_res.data:
            try:
                saved_tasks = json.loads(pending_res.data[0]["text"])
            except Exception:
                pass

        if confirmed and saved_tasks:
            db.table("users").update({"onboarding_step": "done"}).eq("phone", clean_phone).execute()
            try:
                daily_planner.generate_first_plan_from_tasks(updated_user, saved_tasks)
            except Exception as e:
                print(f"Error generating first plan: {e}")
            return ""
        else:
            new_tasks = daily_planner.extract_tasks_from_text(updated_user, message)
            tasks_json = json.dumps(new_tasks, ensure_ascii=False)
            db.table("user_patterns").insert({
                "user_id": updated_user.id,
                "pattern_type": "pending_first_tasks",
                "text": tasks_json,
            }).execute()
            tasks_text = "\n".join(f"{i+1}. {t['title']}" for i, t in enumerate(new_tasks))
            return f"עדכנתי. הנה המשימות החדשות:\n\n{tasks_text}\n\n*מאשר?*"

    return "משהו השתבש. כתוב שלום להתחלה מחדש."
