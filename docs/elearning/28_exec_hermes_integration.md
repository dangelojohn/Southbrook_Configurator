---
course: 28
chapter: 28.6
title: Exec Dashboard Module — Hermes Integration
duration: 6
audience: Developer integrating Hermes recommendations into exec view
prereqs: Lessons 28.1-28.5, Hermes familiarity
custom_modules: southbrook_exec_dashboard, southbrook_hermes
---

# Exec Dashboard Module — Hermes Integration

## The Hermes-flagged tile

```python
@api.model
def get_hermes_flagged_tile(self):
    user_personas = self._user_personas()
    recs = self.env["hermes.recommendation"].search([
        ("state", "=", "pending_review"),
        ("persona", "in", user_personas),
    ])
    
    return {
        "title": "Hermes Awaiting Your Review",
        "value": f"{len(recs)} flagged",
        "subtitle": "Tap to triage",
        "color": "red" if len(recs) > 10 \
                 else "amber" if len(recs) > 0 \
                 else "green",
        "list": [{
            "id": r.id,
            "subject": r.subject,
            "confidence": r.confidence,
            "created_days_ago": (
                fields.Datetime.now() - r.create_date).days,
        } for r in recs[:10]],
        "drill_action": "hermes.action_recommendations",
        "drill_domain": [
            ("state", "=", "pending_review"),
            ("persona", "in", user_personas),
        ],
    }
```

## Personas resolution

```python
@api.model
def _user_personas(self):
    """Return list of persona codes the current user has."""
    user = self.env.user
    personas = []
    if user.has_group("southbrook_hermes.group_hermes_exec"):
        personas.append("exec_owner")
    if user.has_group("southbrook_hermes.group_hermes_mfg_manager"):
        personas.append("mfg_manager")
    if user.has_group("southbrook_hermes.group_hermes_controller"):
        personas.append("controller")
    # ... etc.
    return personas
```

So a user with multiple groups sees recommendations for any of
their personas.

## Inline approve/reject from dashboard

Power users may want to act on recommendations without leaving
the dashboard:

```python
def approve_from_dashboard(self, rec_id):
    rec = self.env["hermes.recommendation"].browse(rec_id)
    if not rec.exists() or rec.state != "pending_review":
        raise UserError(_("Already processed"))
    rec.action_apply()
    return True
```

```javascript
async approveRec(recId) {
    await this.orm.call(
        "southbrook.exec_dashboard.tile",
        "approve_from_dashboard",
        [recId],
    );
    await this.loadTiles();  // Refresh tile
}
```

## Hermes flagged categories

The tile can split by category for finer triage:

```python
return {
    ...,
    "subtitle": f"{n_quality} quality, {n_finance} finance, "
                f"{n_ops} ops",
}
```

User sees the breakdown without opening each.

## When Hermes is unavailable

Defensive handling:

```python
try:
    rec_count = self.env["hermes.recommendation"].search_count(...)
except KeyError:
    # Hermes module not installed; show gracefully
    return {
        "title": "Hermes Awaiting Your Review",
        "value": "N/A",
        "color": "grey",
    }
```

## Common mistakes + how to recover

- **"Tile says '5 flagged' but I'm not in the right group"** —
  persona mismatch. Verify user_personas correctly resolves.
- **"Inline approve from dashboard doesn't reflect"** — refresh
  not called after action. Call `loadTiles()`.
- **"Tile shows 100+"** — backlog accumulated; not a tile bug.
  Triage time.

## Quiz

**Q1.** Hermes-flagged tile colour green / amber / red?

> Green = 0 flagged. Amber = 1-10. Red = 10+ (threshold tuneable).

**Q2.** User in multiple persona groups. Sees what recs?

> Recs targeted to any of their persona codes.

**Q3.** Inline approve / reject — pros vs cons vs drilling to
Hermes Console?

> Pro: faster, fewer clicks. Con: less context for each rec; may
> rush a decision that deserves more review.

**Q4.** Hermes not installed but tile is configured. Effect?

> Should show grey/"N/A" gracefully. Without defensive code, KeyError
> on model lookup.

**Q5.** Recommendation persona = "exec_owner". Tile shows it to whom?

> Users with `group_hermes_exec`. Single persona match suffices.
