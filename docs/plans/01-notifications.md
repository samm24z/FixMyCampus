# 1. Notifications

Status: phase 1 built on `feature/notifications` (2026-10-24), not yet tried against the hosted database (needs migration `20261024_0009`). Phase 2 waits for deployment.

The `notifications` table (`backend/app/models/notification.py`) and its schemas existed since the
first migration, but nothing wrote, served or showed notifications.

## Phase 1: in-app notifications

### Who hears about what

Notifications are staged in the same transaction as the change (like audit rows), so a rolled-back
change never notifies anyone. The person who did the action is never notified about it.

| Event | Recipients | Type |
| --- | --- | --- |
| Ticket filed | active coordinators | `TICKET_CREATED` |
| Status changed (any path, incl. group follow-on and auto-close) | the ticket's reporter | `STATUS_CHANGED` |
| Moved to RESOLVED | the reporter, asked to confirm or reopen | `FEEDBACK_REQUEST` |
| Assigned / reassigned | the new assignee | `ASSIGNED` |
| Reopened by the reporter | the assignee, else coordinators | `STATUS_CHANGED` |
| Reporter confirms the fix | the assignee | `STATUS_CHANGED` |
| Public comment | reporter and assignee | `COMMENT_ADDED` |
| Staff-only note | assignee only (never the reporter) | `COMMENT_ADDED` |
| Rating submitted | the assignee | `FEEDBACK_RECEIVED` |
| SLA warning / breach | see [03-sla-alerts.md](03-sla-alerts.md) | `SLA_WARNING` / `SLA_BREACH` |

Privacy rule: a notification only points at a ticket its recipient can already see
(`permissions.can_view_ticket`), and its text never contains staff-only notes. The service checks
this before staging each row.

### Backend

- `app/services/notification_service.py`: `notify(...)` stages rows; event helpers called from
  `ticket_service` (status changes go through `_record_status`, so every path is covered once).
- `app/api/v1/notifications.py`:
  - `GET /notifications?unread_only=&page=&page_size=` → paginated, newest first, with `ticket_number`.
  - `GET /notifications/unread-count` → `{"count": n}`.
  - `POST /notifications/read` with `{"ids": [...]}` or `{"all": true}` → marks only the caller's rows.
- Read notifications older than `NOTIFICATION_RETENTION_DAYS` (90) are purged by the background loop.
- Tests: every row of the table above, privacy (internal notes, visibility), own-rows-only reads.

### Web

- Bell in the navbar with an unread badge (polls every 60 s and on window focus), dropdown with the
  latest notifications, click opens the ticket and marks it read, "Mark all as read".

### Mobile

- Bell in the tickets tab header with a badge, opening a notifications screen (pull to refresh,
  tap opens the ticket, mark all read). Polls on focus.

## Phase 2: push and email (after deployment)

- `device_tokens` table and `POST/DELETE /devices`; `expo-notifications` registration after sign-in
  (needs an EAS project id and a backend reachable from phones).
- Push sender called after commit (Expo push API), fail-soft, drops tokens that report
  `DeviceNotRegistered`.
- Optional email digest for staff (Resend or SMTP), with a per-user setting.
