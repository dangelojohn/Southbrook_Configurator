# SPDX-License-Identifier: LGPL-3.0-only
"""The unified training index.

A training.item is a *pointer* to a piece of learning content. The content
itself lives elsewhere — a slide.slide row, an ir.attachment PDF, a website
page, or an external URL. The point of this model is to make all of those
findable through a single search box and a single set of tags.

Field anatomy
-------------

- ``source_ref`` — string key identifying the underlying record, e.g.
  ``slide.slide:42`` or ``ir.attachment:1729`` or ``url:https://…``.
  Unique. The post_init_hook keys slides by this format; manually-added
  items use whatever pattern the admin chooses.

- ``url`` — the canonical place the user lands when they click this
  item. ``/slides/slide/<id>`` for slides, ``/web/content/<id>`` for
  attachments, anything for ``kind=external``.

- ``kind`` — coarse type, used for icons + filtering. See KIND_SELECTION.

- ``channel_id`` — backreference to ``slide.channel`` so the kanban
  groups visually mirror the eLearning catalogue.

- ``tag_ids`` — m2m to ``southbrook.training.tag``. The JTBD verb-phrase
  search is "tag of kind jtbd ilike user_query".

- ``role_group_ids`` — gates which users see this item in the Help
  panel and ``/training/recommended``. Empty = visible to everyone.

- ``minutes`` / ``audience`` — short hints shown on the catalogue card.

A note on duplication
---------------------

Yes, ``slide.slide`` already has name + description + channel_id +
tags. We mirror them here on purpose: it lets us add JTBD tags, role
gating, and external content (PDFs, runbooks, web tours) without
patching the Odoo native slide model.  The seed hook keeps the mirror
fresh on every -u of this addon.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


KIND_SELECTION = [
    ("lesson", "Lesson"),
    ("micro", "JTBD Micro"),
    ("course", "Course"),
    ("runbook", "Runbook"),
    ("stepcard", "Step Card"),
    ("video", "Video"),
    ("tour", "In-App Tour"),
    ("external", "External Link"),
]


class SouthbrookTrainingItem(models.Model):
    _name = "southbrook.training.item"
    _description = "Southbrook Training Item"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"

    name = fields.Char(required=True, index=True, tracking=True)
    summary = fields.Text(tracking=True)
    kind = fields.Selection(
        KIND_SELECTION, required=True, default="lesson", tracking=True)
    sequence = fields.Integer(default=10)
    source_ref = fields.Char(
        required=True, index=True, copy=False,
        help="Stable identifier of the underlying record. Examples: "
             "'slide.slide:42', 'ir.attachment:1729', 'url:https://…'.")
    url = fields.Char(required=True, tracking=True)

    @api.constrains("url")
    def _check_url_scheme(self):
        # The Help panel opens url via window.open / act_url. Only curators can
        # write items, but constrain the scheme anyway so a stray "javascript:"
        # can't become a script-execution vector in the panel.
        for rec in self:
            u = (rec.url or "").strip().lower()
            if u and not (u.startswith("http://") or u.startswith("https://")
                          or rec.url.strip().startswith("/")):
                raise ValidationError(_(
                    "Training URL %s must be http(s):// or a leading-slash "
                    "path.") % rec.url)
    channel_id = fields.Many2one(
        "slide.channel", string="eLearning Course",
        ondelete="set null", index=True)
    tag_ids = fields.Many2many(
        "southbrook.training.tag",
        "southbrook_training_item_tag_rel",
        "item_id",
        "tag_id",
        string="Tags",
    )
    role_group_ids = fields.Many2many(
        "res.groups",
        "southbrook_training_item_group_rel",
        "item_id",
        "group_id",
        string="Restricted to Groups",
        help="If set, only users in at least one of these groups will see "
             "this item in the Help panel and /training/recommended. "
             "Leave empty for everyone.")
    minutes = fields.Integer(string="Duration (min)", default=0)
    audience = fields.Char()
    is_active = fields.Boolean(default=True, tracking=True)

    _source_ref_uniq = models.Constraint(
        'UNIQUE(source_ref)',
        "Training items are keyed by source_ref — duplicates not allowed.",
    )

    def open_url(self):
        """Form-header button — opens the item's URL in a new tab.

        Returns an ir.actions.act_url so the Odoo client navigates
        without losing the breadcrumb. ``target='new'`` makes it open
        in a separate tab.
        """
        self.ensure_one()
        if not self.url:
            return False
        return {
            "type": "ir.actions.act_url",
            "url": self.url,
            "target": "new",
        }

    @api.model
    def search_for_user(self, query=None, menu_id=None, limit=8):
        """Convenience used by the Help panel + /training/recommended.

        Returns a list of dicts ready for JSON serialization. Applies the
        role_group_ids gate, the query (ilike on name + summary + JTBD
        tags), and (optionally) a menu filter resolved through
        ``southbrook.training.menu_link``.
        """
        domain = [("is_active", "=", True)]
        user = self.env.user
        # Gate on role groups: include items with NO role gate, OR items
        # gated to at least one group the user is in.
        my_group_ids = user.group_ids.ids
        domain += ["|",
                   ("role_group_ids", "=", False),
                   ("role_group_ids", "in", my_group_ids)]
        if menu_id:
            Link = self.env["southbrook.training.menu_link"].sudo()
            linked = Link.search(
                [("menu_id", "=", menu_id)]).mapped("item_id").ids
            if linked:
                domain += [("id", "in", linked)]
        if query:
            q = query.strip()
            if q:
                # Multi-axis match: name, summary, JTBD tag names. Lots of
                # subqueries but the dataset is small (<5k items even at
                # peak) so this is fine.
                jtbd_tag_ids = self.env["southbrook.training.tag"].search(
                    [("kind", "=", "jtbd"), ("name", "ilike", q)]).ids
                domain += ["|", "|",
                           ("name", "ilike", q),
                           ("summary", "ilike", q),
                           ("tag_ids", "in", jtbd_tag_ids)]
        items = self.sudo().search(domain, limit=limit)
        return [{
            "id": it.id,
            "name": it.name,
            "summary": it.summary or "",
            "kind": it.kind,
            "url": it.url,
            "minutes": it.minutes,
            "audience": it.audience or "",
            "tags": [{"id": t.id, "name": t.name, "kind": t.kind}
                     for t in it.tag_ids],
        } for it in items]
