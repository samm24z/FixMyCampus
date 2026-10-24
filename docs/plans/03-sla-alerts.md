# 3. SLA alerts and escalation

Status: built on `feature/notifications` (2026-10-24) with notifications phase 1. Code: `app/services/sla_service.py`; one-shot `scripts/check_sla_deadlines.py`.

A deadline is set when a ticket is filed (`ticket_service._sla_deadline`), and the admin table shows
an overdue flag, but nobody was alerted and `sla_rules.escalation_threshold_hours` was never read.
Seeded rules: LOW 168 h / warn 144 h, MEDIUM 72 / 48, HIGH 24 / 12, CRITICAL 4 / 2.

## Behaviour

Runs in the existing background loop (`app/main.py`, every `AUTO_CLOSE_INTERVAL_MINUTES`), and as a
one-shot script for cron.

- **Warning:** an open main ticket (not RESOLVED/CLOSED, not grouped under another) whose age has
  passed its rule's `escalation_threshold_hours` and has not been warned → notify the assignee (or
  the coordinators if unassigned) with `SLA_WARNING`; set `tickets.sla_warned_at`.
- **Breach:** an open main ticket past `sla_deadline` and not yet flagged → notify the assignee and
  the coordinators with `SLA_BREACH`; set `tickets.sla_breached_at`; audit row.
- Each alert fires once per deadline. When a coordinator changes the deadline, category or priority,
  both flags reset, so the new deadline gets its own alerts.
- Rows are locked with `SKIP LOCKED`, so two backend workers never send the same alert.
- No automatic priority bump on breach for now (decision for the user).

## Schema

Migration `20261024_0009`: `tickets.sla_warned_at`, `tickets.sla_breached_at` (nullable timestamps).

## Later

- Working hours and holidays in the SLA clock.
- `GET /tickets?overdue=true` and an overdue filter in the staff queue (item 10).
