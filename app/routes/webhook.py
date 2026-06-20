from fastapi import APIRouter, Request, Response
from app.services import context as ctx, ai_coach, whatsapp, onboarding

router = APIRouter()


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    phone = str(form.get("From", ""))
    body = str(form.get("Body", "")).strip()

    if not phone or not body:
        return Response(status_code=204)

    user = ctx.get_user_by_phone(phone)

    if user is None:
        reply = onboarding.start_onboarding(phone)
        whatsapp.send_message(phone, reply)
        return Response(status_code=204)

    if user.onboarding_step != "done":
        reply = onboarding.handle_onboarding(user, body)
        whatsapp.send_message(phone, reply)
        return Response(status_code=204)

    # אם המשתמש היה מושהה – חדש פעילות
    if getattr(user, 'paused_at', None):
        from app.database.supabase import get_db as _get_db
        _get_db().table("users").update({"paused_at": None}).eq("id", user.id).execute()
        whatsapp.send_message(phone, f"שמח שחזרת {user.name or ''}! ממשיכים מחר בבוקר בשמונה.")

    context = ctx.build_context(phone)
    if not context:
        return Response(status_code=204)

    ctx.save_interaction(user.id, "user", body)

    result = ai_coach.chat(
        user=context["user"],
        message=body,
        tasks=context["tasks"],
        today_plan=context["today_plan"],
        recent_history=context["recent_history"],
        patterns_summary=context["patterns_summary"],
        completion_rate_7d=context["completion_rate_7d"],
    )

    _apply_actions(context, result.get("actions", []))

    reply_msg = result.get("message", "")
    if reply_msg:
        whatsapp.send_message(phone, reply_msg)
        ctx.save_interaction(
            user.id, "assistant", reply_msg,
            sentiment=result.get("mood_score")
        )

    return Response(status_code=204)


def _apply_actions(context: dict, actions: list[dict]):
    tasks = context["tasks"]
    today_plan = context["today_plan"]
    user = context["user"]

    for action in actions:
        atype = action.get("type")

        if atype == "update_task":
            task_num = action.get("task_num")
            status = action.get("status", "completed")
            notes = action.get("notes")
            difficulty = action.get("difficulty")
            matching = [t for t in tasks if t.order_num == task_num]
            if matching:
                ctx.update_task_status(matching[0].id, status, notes, difficulty)
            if today_plan:
                ctx.recalc_completion_rate(today_plan.id)

        elif atype == "update_mood":
            if today_plan:
                ctx.update_plan_mood(today_plan.id, action.get("score", 3))

        elif atype == "add_insight":
            text = action.get("text")
            if text:
                ctx.save_pattern(user.id, "ai_insight", text)

        elif atype == "add_task":
            title = action.get("title")
            category = action.get("category")
            if title and today_plan:
                from app.database.supabase import get_db
                db = get_db()
                next_order = max((t.order_num for t in tasks), default=0) + 1
                db.table("tasks").insert({
                    "daily_plan_id": today_plan.id,
                    "user_id": user.id,
                    "title": title,
                    "category": category,
                    "order_num": next_order,
                }).execute()

        elif atype == "schedule_followup":
            from app.database.supabase import get_db
            from datetime import datetime, timedelta, timezone
            task_num = action.get("task_num")
            matching = [t for t in tasks if t.order_num == task_num]
            if matching:
                db = get_db()
                followup_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
                db.table("tasks").update({
                    "follow_up_scheduled_at": followup_at,
                    "follow_up_count": 0,
                }).eq("id", matching[0].id).execute()
