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
    # v18+ merged check_access_rights + check_access_rule into a single
    # check_access(operation); the old pair is deprecated and spams the
    # test log with multi-frame DeprecationWarning tracebacks.
    record.check_access("write")
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
    order.check_access("read")
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
    # check_access(operation) does both ACL + record-rule scope per spec § 4.4
    order.check_access("read")
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
def propose_recommendation(env, intent: str, payload: dict, summary: str,
                            partner_id: int = None, persona: str = None,
                            name: str = None):
    # persona + partner_id are AUTHORITATIVELY set by the dispatch controller
    # from verified JWT claims (see hermes_tools_api.py). Any caller-supplied
    # values for these args are overridden by the controller before this fn
    # runs, so the LLM cannot lift its own intent-guard or attribute the
    # recommendation to another partner.
    import json
    if persona == "trade_partner" and intent not in _TRADE_PARTNER_INTENTS:
        raise UserError(
            f"Trade partners cannot propose '{intent}' recommendations. "
            f"Allowed intents: {', '.join(_TRADE_PARTNER_INTENTS)}.")
    if not partner_id:
        # Fall back to env.user.partner_id when the dispatch controller didn't
        # inject — happens only in direct in-process tests that bypass dispatch.
        partner_id = env.user.partner_id.id
    Rec = env["southbrook.hermes.recommendation"]
    full_payload = {"intent": intent, "data": payload or {}}
    # sudo() is the spec § 4.4 "explicitly tier-gated T2 tools with a
    # documented reason" carve-out: a draft recommendation is owned by
    # the Fabio agent partner, not by the requesting partner, and must
    # be visible to Southbrook reviewers via record rules that don't
    # match the requesting portal user.
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


@hermes_tool(
    personas=["sales_rep", "mfg_manager"],
    tier="T2", scope="own_order",
    description=(
        "Draft an internal note on the given sale.order that mocks up an "
        "email to the customer — subject + body. The note is posted as an "
        "internal message (NOT sent as email) so a human sales rep or "
        "manager can review and either edit + click Send by Email OR "
        "reject. Use for 'draft a follow-up email' or 'compose a status "
        "update to Richwood on order S00123'."),
    parameters={
        "order_id": {"type": "integer", "required": True},
        "subject": {"type": "string", "required": True},
        "body": {"type": "string", "required": True,
                 "description": "The proposed email body. Plain text or "
                                "simple HTML (mail.message will "
                                "sanitize). Keep under 2000 chars."},
    },
)
def draft_customer_email(env, order_id, subject, body):
    # SECURITY: run as the acting user and enforce write access on THIS order
    # (not sudo). The tool declares scope="own_order" but previously sudo-browsed
    # any order_id with no check — an LLM (steerable via prompt-injection planted
    # in an order thread Fabio reads) could post a note onto ANY order in the DB.
    # Mirrors post_internal_note / send_spec_pdf_email.
    order = env["sale.order"].browse(order_id)
    if not order.exists():
        return {"error": "order_not_found"}
    order.check_access_rights("write")
    order.check_access_rule("write")
    # Trim + truncate subject to 1-256 chars
    subject_clean = (subject or "").strip()[:256]
    # Trim + truncate body to 1-2000 chars
    body_clean = (body or "").strip()[:2000]
    if not body_clean:
        return {"error": "empty_body"}
    # Compose marker-prefixed note so a human reviewer can see this is a
    # Fabio draft, not a message the customer already received.
    marker_body = (
        "📝 <b>Fabio-drafted customer email "
        "(NOT SENT — review before delivering)</b><br/><br/>"
        f"<b>Subject:</b> {subject_clean}<br/><br/>"
        "<hr/>"
        f"{body_clean}"
    )
    message = order.message_post(
        body=marker_body,
        subject=subject_clean,
        message_type="comment",
        subtype_xmlid="mail.mt_note",
    )
    result = {
        "ok": True,
        "order_id": order.id,
        "order_name": order.name,
        "message_id": message.id,
        "human_review_required": True,
        "note": ("Draft email posted to the order thread as an internal "
                 "note. Sales rep can open the order in Odoo and click "
                 "'Send by Email' to deliver, or reject the draft."),
    }
    if not (order.partner_id and order.partner_id.email):
        result["warning"] = "customer has no email on file"
    return result
