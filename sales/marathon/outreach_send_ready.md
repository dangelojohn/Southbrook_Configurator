# Marathon outreach — send-ready

Three artifacts: (1) the email to send after the warm intro lands, (2) a follow-up
nudge for 5 business days later if no response, (3) a meeting-prep one-pager
to attach when the meeting is booked.

Replace `[[INTRO_NAME]]`, `[[RECIPIENT_NAME]]`, `[[RECIPIENT_ROLE]]` with the
real values before sending. Leaves Variant A (channel-mechanic-led) intact
as the primary — it's the most concrete framing of the three.

---

## 1. The send email (use after the warm intro)

> **To:** [[RECIPIENT_NAME]] <[[RECIPIENT_EMAIL]]>
> **Cc:** [[INTRO_NAME]]
> **Subject:** Marathon as the default hardware catalog on a live cabinet-shop SaaS

[[RECIPIENT_NAME]] —

Following up on [[INTRO_NAME]]'s note. Quick context, then a concrete ask.

Southbrook Cabinetry has been running a workflow platform we call **KitchenForge** on our own shop for the past year — quoting, cut-spec, hardware resolver, the full surface. It's live at **southbrookcabinetry.space** and you can poke around the demo today. We've productized it for other independent cabinet shops, and the Marathon integration is already scaffolded in code: partner record, 20 finishes, CSV import, hardware resolver. This is not a roadmap pitch.

The channel mechanic:

- Marathon's catalog becomes the **default hardware library** on every shop on the channel tier
- Channel tier pricing: **$149/mo per shop**, 60/40 split (Southbrook/Marathon)
- **$8 USD rebate** per Marathon-spec'd cabinet, reconciled monthly
- Marathon collects **real-time spec telemetry** — demand signal 60+ days before the PO
- **6-month category exclusivity** on cabinet-hardware
- Conservative 12-month case: **~$1M ARR** through the channel + 7-figure hardware pull-through

I'd like 30 minutes to walk you through (a) the integration we've already built and (b) the 90-day pilot plan starting with 5 friendly shops in your flagship region.

What does next week look like?

John D'Angelo
Southbrook Cabinetry
dangelo.john@gmail.com
southbrookcabinetry.space

---

## 2. Follow-up nudge (send 5 business days later if no reply)

> **Subject:** Re: Marathon as the default hardware catalog on a live cabinet-shop SaaS

[[RECIPIENT_NAME]] —

Quick nudge. The technical integration is already shipped — partner record, finishes, CSV import, hardware resolver, auto-RFQ, telemetry — so this is genuinely a 30-minute "should we pilot this?" call, not a discovery one.

If you'd rather a forward-and-have-your-team-look-first, I've attached a 1-page technical brief written for your CTO / IT lead.

Happy to defer to whatever cadence works on your end.

John

---

## 3. Meeting-prep one-pager (attach when meeting is booked)

See `sales/marathon/one_pager.md` and `sales/marathon/technical_appendix.md` —
both are designed to print clean on a single page each. Recommend sending
**one_pager** to [[RECIPIENT_NAME]] and **technical_appendix** to whichever
IT/CTO contact they delegate the integration review to.

For the meeting itself, the deck is at `sales/marathon/pitch_deck.md` (8 slides,
each with speaker notes). Suggested 30-min flow:

| Min | Section | Slides |
|---|---|---|
| 0–5 | The broken hour + what we built | 1–2 |
| 5–15 | The mechanic (telemetry + spec-in + auto-RFQ) | 3–4 |
| 15–20 | Numbers + proof | 5–6 |
| 20–25 | 90-day pilot path | 7 |
| 25–30 | Ask + close | 8 |

The ROI calculator at `sales/marathon/roi_calculator.md` is the document
their CFO will ask for after the meeting. It carries conservative / base /
aggressive scenarios with the math fully exposed.

---

## Pre-send checklist

- [ ] Replace `[[INTRO_NAME]]`, `[[RECIPIENT_NAME]]`, `[[RECIPIENT_EMAIL]]`, `[[RECIPIENT_ROLE]]`
- [ ] Confirm [[INTRO_NAME]] has actually made the warm intro (don't cold-send this template)
- [ ] Send from `dangelo.john@gmail.com` or your Southbrook address
- [ ] Subject line is the load-bearing element — don't shorten it
- [ ] Attach nothing on the first email (links to live site instead)
- [ ] Calendar 5 business days from send for the follow-up nudge
