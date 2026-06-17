---
course: <course number — matches README.md table>
chapter: <e.g. 1.3>
title: <verb-first, role-anchored — e.g. "CNC Operator — Your Daily Flow">
duration: <minutes>
audience: <one-sentence concrete role>
prereqs: <previous lessons + any non-Southbrook knowledge assumed>
custom_modules: <comma-separated list of southbrook_* modules this lesson covers>
---

# <Title repeated as H1>

## Who this lesson is for

<2-3 sentences. Concrete. "You're the operator at..." or "You schedule MOs
against...". Do not say "this lesson is for anyone interested in...".>

## Where this lives on the site

<Exact menu path. Use the > arrow notation. Include the touchscreen /
shop-floor alternate path if one exists.>

## What your screen shows

<Bullet list of fields the trainee will see. For each field, reference the
model + field name in code in parentheses so a developer reading the
lesson can trace it back. Example:>

- **Setup time** (`x_sbk_default_setup_time_min` on `mrp.workcenter`) — what it means in the user's words.

## Your daily flow

<Numbered phases (Start of shift / Per-job loop / End of shift), each with
sub-bullets of the exact taps + decisions. Use the words the user uses.>

## Common mistakes + how to recover

<3-5 entries. Each is a quoted problem from the user's mouth, then a
concrete recovery procedure. This is the most valuable section of every
lesson — it's where a trained user differs from someone following steps.>

## What the system is doing behind the scenes

<Optional reading. One paragraph technical. Which tables get written.
Which agent loops will react. Useful for the curious operator and
essential for the supervisor debugging an incident.>

## Quiz (5 questions, applied)

<Five questions. Each is a scenario from the lesson, not a definition
quiz. "Your CNC operator says... what do you check first?" not "What is
the difference between..."  Provide the answer right after the question
as a blockquote so the slide can show / hide it.>

## What this lesson does NOT cover

<Pointer to adjacent lessons + native Odoo training for everything that's
out of scope. Keeps the lesson focused.>
