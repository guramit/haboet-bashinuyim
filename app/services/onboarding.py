import anthropic
import os
import json
from app.database.supabase import get_db
from app.models.user import User
from app.services import whatsapp, daily_planner

STEPS = ["name", "business_name", "business_field", "challenges", "gender", "focus", "done"]

FOCUS_OPTIONS = ["מכירות", "שיווק", "ניהול כספי", "ניהול זמן", "שגרה", "לקוחות", "צוות"]


def start_onboarding(phone: str) -> str:
    db = get_db()
    clean = phone.replace("whatsapp:", "")
    db.table("users").insert({"phone": clean, "onboarding_step": "name"}).execute()
    return (
        "שלום, ברוך הבא לבועט בישבנים.\n\n"
        "אני עוזר עסקי AI. כל בוקר אשלח לך 3 משימות ממוקדות לעסק, "
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


def _detect_gender(name: str, message: str) -> str | None:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=50,
        messages=[{"role": "user", "content": f"זהה מין (זכר/נקבה) לפי השם '{name}' ו/או הטקסט: '{message}'. החזר JSON בלבד: {{\"gender\": \"male\"}} או {{\"gender\": \"female\"}} או {{\"gender\": null}} אם לא ברור."}],
    )
    try:
        return json.loads(resp.content[0].text).get("gender")
    except Exception:
        return None


def handle_onboarding(user: User, message: str) -> str:
    db = get_db()
    step = user.onboarding_step
    clean_phone = user.phone

    if step == "name":
        name = message.strip()
        gender = _detect_gender(name, message)
        update = {"name": name, "onboarding_step": "business_name"}
        if gender:
            update["gender"] = gender
        db.table("users").update(update).eq("phone", clean_phone).execute()
        return f"נעים מאוד, {name}!\n\n*האם לעסק שלך יש שם או מותג נפרד מהשם שלך?*\n(אם כן – כתוב אותו. אם לא – כתוב 'לא')"

    elif step == "business_name":
        msg = message.strip()
        if msg.lower() in ["לא", "no", "-", "אין"]:
            biz_name = user.name
        else:
            biz_name = msg
        db.table("users").update({"business_name": biz_name, "onboarding_step": "business_field"}).eq("phone", clean_phone).execute()
        return f"*{biz_name}* – *באיזה תחום פועל העסק?*\n(לדוגמה: קמעונאות, שירותים, טכנולוגיה, בריאות, אוכל...)"

    elif step == "business_field":
        db.table("users").update({"business_field": message.strip(), "onboarding_step": "challenges"}).eq("phone", clean_phone).execute()
        return "*מה האתגרים העיקריים שאתה מתמודד איתם בעסק?*\n\n(כתוב בחופשיות – לדוגמה: מציאת לקוחות, ניהול זמן, שיווק, תזרים מזומנים...)"

    elif step == "challenges":
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            messages=[{"role": "user", "content": f"חלץ רשימת אתגרים עיקריים מהטקסט הבא. החזר JSON בלבד: {{\"challenges\": [\"...\", \"...\"]}}\n\nטקסט: {message}"}],
        )
        try:
            data = json.loads(resp.content[0].text)
            challenges = data.get("challenges", [message.strip()])
        except Exception:
            challenges = [message.strip()]

        # נסה לזהות מין מתוך הכתיבה אם עדיין לא ידוע
        gender_update = {}
        current_gender = user.gender
        if not current_gender:
            detected = _detect_gender(user.name or "", message)
            if detected:
                gender_update["gender"] = detected
                current_gender = detected

        db.table("users").update({"main_challenges": challenges, **gender_update}).eq("phone", clean_phone).execute()

        # אם כבר זיהינו מין – דלג על שאלת המין
        if current_gender:
            db.table("users").update({"onboarding_step": "focus"}).eq("phone", clean_phone).execute()
            options = "\n".join(f"• {f}" for f in FOCUS_OPTIONS)
            return f"*באילו תחומים תרצה להתמקד?*\n\n{options}\n\n(כתוב את התחומים שבחרת, מופרדים בפסיקה)"

        db.table("users").update({"onboarding_step": "gender"}).eq("phone", clean_phone).execute()
        return "שאלה אחת לפני שמתחילים –\n*איך לפנות אליך? זכר או נקבה?*"

    elif step == "gender":
        msg = message.strip().lower()
        if any(w in msg for w in ["נקבה", "אישה", "בת", "female", "f"]):
            gender = "female"
        else:
            gender = "male"
        db.table("users").update({"gender": gender, "onboarding_step": "focus"}).eq("phone", clean_phone).execute()
        options = "\n".join(f"• {f}" for f in FOCUS_OPTIONS)
        return f"*באילו תחומים תרצה להתמקד?*\n\n{options}\n\n(כתוב את התחומים שבחרת, מופרדים בפסיקה)"

    elif step == "focus":
        chosen = [f.strip() for f in message.replace("،", ",").split(",") if f.strip()]
        if not chosen:
            chosen = ["מכירות"]
        db.table("users").update({"focus_areas": chosen, "onboarding_step": "done"}).eq("phone", clean_phone).execute()

        updated_res = db.table("users").select("*").eq("phone", clean_phone).limit(1).execute()
        updated_user = User.from_dict(updated_res.data[0])
        try:
            daily_planner.generate_daily_plan(updated_user)
        except Exception as e:
            print(f"Error generating first plan: {e}")

        return f"מושלם! הפרופיל שלך מוכן.\n\nהתוכנית הראשונה שלך נשלחת עכשיו!\nמחר בשעה 8:00 תקבל תוכנית יומית חדשה אוטומטית.\n\n*בהצלחה {updated_user.name}!*"

    return "משהו השתבש. כתוב שלום להתחלה מחדש."
