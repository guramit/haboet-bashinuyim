from app.database.supabase import get_db
from app.models.user import User
from app.services import whatsapp, daily_planner

STEPS = ["name", "business_name", "business_field", "challenges", "commitment", "focus", "done"]

FOCUS_OPTIONS = ["מכירות", "שיווק", "ניהול כספי", "ניהול זמן", "שגרה", "לקוחות", "צוות"]


def start_onboarding(phone: str) -> str:
    db = get_db()
    clean = phone.replace("whatsapp:", "")
    db.table("users").insert({"phone": clean, "onboarding_step": "name"}).execute()
    return (
        "שלום, ברוך הבא להבועט בשינויים.\n\n"
        "אני מאמן אישי AI לבעלי עסקים. כל בוקר אשלח לך 3 משימות ממוקדות לעסק, "
        "אעקוב אחרי הביצוע שלך במהלך היום, ואהיה זמין לשיחה חופשית בכל עת.\n\n"
        "מה אני יכול לעשות:\n"
        "— תכנית עבודה יומית מותאמת אישית\n"
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
        db.table("users").update({"name": message.strip(), "onboarding_step": "business_name"}).eq("phone", clean_phone).execute()
        return f"נעים מאוד, {message.strip()}! 💪\n\n*מה שם העסק שלך?*"

    elif step == "business_name":
        db.table("users").update({"business_name": message.strip(), "onboarding_step": "business_field"}).eq("phone", clean_phone).execute()
        return f"מעולה! *{message.strip()}* 🎯\n\n*באיזה תחום פועל העסק?*\n(לדוגמה: קמעונאות, שירותים, טכנולוגיה, בריאות, אוכל...)"

    elif step == "business_field":
        db.table("users").update({"business_field": message.strip(), "onboarding_step": "challenges"}).eq("phone", clean_phone).execute()
        return "*מה האתגרים העיקריים שאתה מתמודד איתם בעסק?*\n\n(כתוב בחופשיות – לדוגמה: מציאת לקוחות, ניהול זמן, שיווק, תזרים מזומנים...)"

    elif step == "challenges":
        import anthropic, os, json
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

        db.table("users").update({"main_challenges": challenges, "onboarding_step": "commitment"}).eq("phone", clean_phone).execute()
        return "*כמה דקות ביום אתה יכול להקדיש למשימות העסק?*\n\n(כתוב מספר – לדוגמה: 30, 60, 90)"

    elif step == "commitment":
        try:
            minutes = int("".join(filter(str.isdigit, message)) or "30")
        except ValueError:
            minutes = 30
        db.table("users").update({"daily_commitment": minutes, "onboarding_step": "focus"}).eq("phone", clean_phone).execute()
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

        return f"מושלם! הפרופיל שלך מוכן 🎉\n\nהתוכנית הראשונה שלך נשלחת עכשיו!\nמחר בשעה 7:00 תקבל תוכנית יומית חדשה אוטומטית.\n\n*בהצלחה {updated_user.name}! 🚀*"

    return "משהו השתבש. כתוב שלום להתחלה מחדש."
