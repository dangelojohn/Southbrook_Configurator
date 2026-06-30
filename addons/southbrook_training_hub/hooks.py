# SPDX-License-Identifier: LGPL-3.0-only
"""post_init_hook — populate ``southbrook.training.item`` from existing slides.

Runs once on install. Idempotent: each slide.slide is keyed by its xml_id-ish
``source_ref`` so re-running -i on a fresh DB doesn't duplicate, and re-running
-u against a populated DB doesn't either (the controller and the systray rely
on the item table, but slides keep loading from their own data files
unchanged).
"""
import logging

_logger = logging.getLogger(__name__)


def _seed_training_items_from_slides(env):
    """Mirror every published slide.slide into southbrook.training.item.

    The catalogue is owned by ``southbrook_elearning_internal``; this hook
    only INDEXES — it never creates, edits, or deletes slides themselves.
    """
    Item = env["southbrook.training.item"].sudo()
    Slide = env["slide.slide"].sudo()
    Tag = env["southbrook.training.tag"].sudo()

    course_tag_cache = {}

    def _tag_for_course(channel):
        if channel.id in course_tag_cache:
            return course_tag_cache[channel.id]
        name = (channel.name or "").strip() or f"Course {channel.id}"
        existing = Tag.search(
            [("kind", "=", "course"), ("name", "=", name)], limit=1)
        if not existing:
            existing = Tag.create({
                "name": name,
                "kind": "course",
                "description": (channel.description or "")[:300],
            })
        course_tag_cache[channel.id] = existing
        return existing

    seeded = 0
    for slide in Slide.search([("is_published", "=", True)]):
        source_ref = f"slide.slide:{slide.id}"
        if Item.search_count([("source_ref", "=", source_ref)]):
            continue
        title = slide.name or f"Slide #{slide.id}"
        item_vals = {
            "name": title,
            "kind": "lesson",
            "source_ref": source_ref,
            "url": f"/slides/slide/{slide.id}",
            "summary": (slide.description or "")[:300],
            "channel_id": slide.channel_id.id,
            "is_active": True,
        }
        if slide.channel_id:
            tag = _tag_for_course(slide.channel_id)
            item_vals["tag_ids"] = [(6, 0, [tag.id])]
        Item.create(item_vals)
        seeded += 1
    _logger.info(
        "southbrook_training_hub: seeded %d training items from slide.slide",
        seeded)
