# SPDX-License-Identifier: LGPL-3.0-only
"""Write tools — T0 (note posting), T1 (email/activity)."""
import datetime

from odoo.exceptions import UserError

from .decorator import hermes_tool


@hermes_tool(
    personas=["trade_partner", "sales_rep", "mfg_manager"],
    tier="T0", scope="own",
    description=(
        "Post an internal note on a record the caller can access. "
        "Used for 'log my preference' or 'remind me later' use cases."),
)
def post_internal_note(env, record_model: str, record_id: int, content: str):
    allowed_models = ("sale.order", "project.task", "southbrook.hermes.question")
    if record_model not in allowed_models:
        raise UserError(
            f"Hermes can't post notes on '{record_model}'. "
            f"Allowed: {', '.join(allowed_models)}.")
    record = env[record_model].browse(record_id)
    record.check_access_rights("write")
    record.check_access_rule("write")
    msg = record.message_post(
        body=content, message_type="comment",
        subtype_xmlid="mail.mt_note")
    return {"ok": True, "message_id": msg.id}


@hermes_tool(
    personas=["trade_partner", "sales_rep"],
    tier="T1", scope="own_order",
    description=(
        "Resend the spec sheet PDF for this order to the requesting partner's "
        "own email address. No customer or third party recipient allowed."),
)
def send_spec_pdf_email(env, order_id: int):
    order = env["sale.order"].browse(order_id)
    order.check_access_rights("read")
    order.check_access_rule("read")
    template = env.ref(
        "sale.email_template_edi_sale", raise_if_not_found=False)
    if not template:
        raise UserError("Standard sale email template not available.")
    target_email = env.user.email or order.partner_id.email
    template.send_mail(order.id, force_send=False, email_values={
        "email_to": target_email,
    })
    return {"ok": True, "sent_to": target_email}


@hermes_tool(
    personas=["trade_partner", "sales_rep", "mfg_manager"],
    tier="T1", scope="own",
    description=(
        "Schedule a follow-up activity (to-do) on the caller's user for the "
        "given order. Due date must be today or later."),
)
def schedule_followup_activity(env, order_id: int, summary: str, due_date: str):
    parsed_date = datetime.date.fromisoformat(due_date)
    if parsed_date < datetime.date.today():
        raise UserError("Activity due_date must be today or in the future.")
    order = env["sale.order"].browse(order_id)
    order.check_access_rights("read")
    activity_type = env.ref("mail.mail_activity_data_todo")
    activity = env["mail.activity"].create({
        "res_id": order.id,
        "res_model_id": env["ir.model"]._get("sale.order").id,
        "activity_type_id": activity_type.id,
        "summary": summary,
        "date_deadline": due_date,
        "user_id": env.user.id,
    })
    return {"ok": True, "activity_id": activity.id}


# Trade-partner intents — encoded as the recommendation's payload `intent`
# key. The actual southbrook.hermes.recommendation.recommendation_type
# selection (`task`/`risk`/`note`/`followup`) is set conservatively to
# `task` so the existing approve→apply pipeline creates a project.task
# for a Southbrook user to action.
_TRADE_PARTNER_INTENTS = (
    "request_revision",
    "request_install_reschedule",
    "request_clarification",
)


@hermes_tool(
    personas=["trade_partner", "sales_rep", "mfg_manager"],
    tier="T2", scope="own",
    description=(
        "Create a draft southbrook.hermes.recommendation for human review. "
        "The actual business mutation only happens when an approver clicks "
        "Approve. For trade-partner persona, only request_revision, "
        "request_install_reschedule, and request_clarification intents "
        "are allowed."),
)
def propose_recommendation(env, partner_id: int, intent: str, payload: dict,
                            summary: str, persona: str = "trade_partner",
                            name: str = None):
    import json
    if persona == "trade_partner" and intent not in _TRADE_PARTNER_INTENTS:
        raise UserError(
            f"Trade partners cannot propose '{intent}' recommendations. "
            f"Allowed intents: {', '.join(_TRADE_PARTNER_INTENTS)}.")
    Rec = env["southbrook.hermes.recommendation"]
    # Encode the intent + caller payload in payload_json so the approve→
    # apply pipeline preserves what the partner asked for.
    full_payload = {"intent": intent, "data": payload or {}}
    rec = Rec.sudo().create({
        "name": name or f"Hermes/{intent}/{summary[:48]}",
        "summary": summary,
        "recommendation_type": "task",
        "payload_json": json.dumps(full_payload, default=str),
        "source_model": "res.partner",
        "source_res_id": partner_id,
        "state": "draft",
    })
    return {"ok": True, "rec_id": rec.id, "summary": summary, "intent": intent}
