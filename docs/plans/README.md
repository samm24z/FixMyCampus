# Roadmap

Enhancements agreed on 2026-10-24, ranked. Each item gets its own plan file when work on it starts;
until then its section here is the plan. Status: `todo`, `in progress`, `done`, `blocked`.

| # | Item | Status | Plan |
| --- | --- | --- | --- |
| 1 | Notifications (in-app, then push) | phase 1 built, phase 2 blocked (deployment) | [01-notifications.md](01-notifications.md) |
| 2 | Automatic routing by place × category | todo | [02-auto-routing.md](02-auto-routing.md) |
| 3 | SLA alerts and escalation | built | [03-sla-alerts.md](03-sla-alerts.md) |
| 4 | Agentic chatbot for staff and coordinators | todo | below |
| 5 | "Someone already reported this" check before submitting | todo | below |
| 6 | Analytics dashboard | todo | below |
| 7 | QR codes per room or block | todo (needs room data) | below |
| 8 | Staff mode on mobile, with before/after photos | todo | below |
| 9 | Admin screens for departments, categories and SLA rules | todo | below |
| 10 | Better staff queue (sort by SLA, filters, bulk actions) | todo | below |
| 11 | Known-issues board | todo | below |
| 12 | Video uploads | blocked (hosting) | `~/.claude/plans/what-are-the-planned-witty-marshmallow.md` |
| 13 | Deployment | blocked (hosting choice) | below |
| 14 | Shared web/mobile TypeScript package | todo | below |
| 15 | Android test pass and web end-to-end tests | todo | below |
| 16 | Shared rate limits (off in-process memory) | todo | below |

Items 1–3 together finish the core loop: a report reaches the right person, and everyone hears back.

---

## 4. Agentic chatbot for staff and coordinators

Today the assistant makes one model call per message and only proposes actions on the student's own
tickets (`backend/app/services/assistant_service.py`).

- **Staff tools:** list my open / overdue tickets, move a ticket forward with a note, summarise a
  ticket's thread, draft a resolution note.
- **Coordinator tools:** "triage the newest tickets" returns a batch of proposed assignments
  (using routing from item 2) that the coordinator approves in one go.
- Multi-step answers with Gemini function calling: read-only tools run freely, any change is still a
  proposal card the person clicks.
- Every tool calls `ticket_service` with the requesting `User`, so it inherits RBAC and audit logging.
- Done when: staff and coordinators get role-specific tools, the eval script covers them, and
  no tool can touch a ticket the user can't see (tests).

## 5. "Someone already reported this" check

Embeddings are compared only after a ticket is filed (`suggestion_service._group_similar`).

- `POST /tickets/similar` with title, description and place returns up to 3 open matches.
- Students see place, status and how long ago only, never names or full descriptions (decision for
  the user: confirm this privacy line).
- The report form (web and mobile) and the chatbot offer "Me too" instead of a new ticket; "Me too"
  files a ticket that joins the group at once, so report counts and escalation still work.
- Done when: the check runs while typing (debounced), fails soft without embeddings, and is tested.

## 6. Analytics dashboard

`backend/app/schemas/analytics.py` defines the shapes; nothing uses them.

- `GET /analytics` (coordinator/admin): tickets by category and by block, average resolution time,
  SLA compliance, satisfaction ratings, staff workload, trend over the last 8 weeks.
- Admin page section with charts (Recharts), filter by date range.

## 7. QR codes per room or block

- `/report?place=<key>&room=<room>` deep link on web and `fixmycampus://report?...` on mobile prefill
  the place.
- Admin page prints a sheet of QR codes per place (and per room once `rooms.csv` is filled).

## 8. Staff mode on mobile

- Staff sign-in shows "My work": assigned tickets sorted by SLA, start work, add a comment, resolve
  with a required note and an optional "after" photo.
- Reporters see before/after photos on the resolved ticket.

## 9. Admin screens for reference data

- CRUD for departments, categories and SLA rules (categories are a fixed enum today in
  `backend/app/models/enums.py`). Moving categories to the database touches the AI prompts and keyword
  fallback, so plan it with item 2.

## 10. Better staff queue

- Sort by SLA deadline by default, filters (status, priority, place), overdue highlighting, bulk
  "start work" for coordinators. `ticket_service.list_tickets` needs a `sort` parameter.

## 11. Known-issues board

- Coordinators mark a main ticket as a public known issue with a short public note. Everyone signed in
  sees the board on the dashboard and in the chatbot ("Wi-Fi down in CSE Block, being fixed").

## 13. Deployment

Blocks push notifications (item 1 phase 2), mobile use off the LAN, and relying on the free Supabase
tier, which pauses after about a week idle. Options were compared on 2026-10-20 (Azure student VM,
VPS, Railway and others). Needs the user's choice.

## 14. Shared web/mobile TypeScript package

`mobile/src/lib/{api,tickets,places,account,assistant}.ts` are hand copies of `frontend/src/lib/*`.
Move the platform-free parts (types, API calls, formatting) to `packages/shared` in an npm workspace.

## 15. Testing

- Run the mobile app on Android (needs Android Studio), checking the chat keyboard, EXIF, picker.
- Playwright end-to-end tests for the main web flows (report, triage, resolve, confirm).

## 16. Shared rate limits

The assistant, media and upload rate limits are per-process dictionaries. Move them to Postgres (or
Redis) before running more than one backend worker.
