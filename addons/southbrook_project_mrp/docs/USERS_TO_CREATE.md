# B1 — Shop-floor users to create (HAND-OFF, deferred)

Account creation is **out of scope** for this module (no credential handling,
no security-group changes). The live instance has only `Administrator` and the
`ProductGraph MCP Bot` as assignable internal users, so the MRP manager has no
real person to hold accountable. An admin should create the following internal
users (Settings → Users), then they become selectable as task **Responsible PM**
(`pm_id`), task Assignees, and MO **Responsible**.

| Name | Role | Suggested login / email | Stage(s) owned |
|------|------|--------------------------|----------------|
| (Floor Manager) | Production / Floor Manager — default **Responsible PM** | floor.manager@southbrookcabinetry.local | all (owns the job) |
| (Cutting operator) | CNC / Cutting & Machining | cutting@southbrookcabinetry.local | Cutting & Machining |
| (Assembly operator) | Assembly | assembly@southbrookcabinetry.local | Assembly |
| (Finishing operator) | Finishing / Paint | finishing@southbrookcabinetry.local | Finishing |
| (Install lead) | Delivery & Install / site measure | install@southbrookcabinetry.local | Delivery & Install |

Notes:
- Give them the **Project / User** and **Manufacturing / User** groups so they
  appear in both Assignees and MO Responsible. (Group assignment is the admin's
  call — this module does not modify groups.)
- `MPM2` referenced in MO chatter is not a user on this instance; create the
  Floor Manager above to fill that role.
- Once created, set each customer-job task's **Responsible PM** to the Floor
  Manager (or the owning lead).
