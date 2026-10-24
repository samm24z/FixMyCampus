# 2. Automatic routing by place × category

Status: todo. Decision approved by the user on 2026-10-19: when place × category clearly matches one
responsible person, assign automatically and notify them; otherwise send to a coordinator.

The templates exist (`data/campus/templates/rooms.csv`, `people.csv`, with `_example` versions), but
`people.csv` has only headers and there is no importer or routing code.

## Data

- `rooms` table: `place_key`, `floor`, `room_name`, `room_type`, `department_code`, `notes`.
- `responsibilities` table: `user_id`, `place_key` (or `*` for campus-wide), `category`,
  `is_backup`, `working_hours` (text for now), `active`.
- Importer `backend/scripts/import_campus_data.py --rooms rooms.csv --people people.csv [--dry-run]`:
  - People are matched to accounts by email; unknown emails are reported, not created (accounts are
    admin-created through Supabase).
  - Validates place keys against `app/core/campus.py`, categories against the category list.
  - Idempotent: re-running replaces that person's responsibilities.

## Routing

- Runs after AI analysis (`suggestion_service.analyze_ticket`), using the confirmed or suggested
  category and the ticket's place.
- Exactly one active primary match with a department → assign through
  `ticket_service.assign_ticket` logic as the system actor (audit `ASSIGNMENT`, actor NULL, note
  "Assigned automatically: <place> × <category>"), which also notifies the assignee.
- No match, several matches, or low AI confidence (< `ROUTING_MIN_CONFIDENCE`) → stays NEW for a
  coordinator, with the candidates shown on the ticket page.
- Backup person is used when the primary is deactivated.
- Setting `AUTO_ROUTING_ENABLED` (default on once data is imported).

## UI

- Ticket page (coordinator): "Routed automatically" badge, or the list of candidates.
- Admin page: who covers which places and categories, with gaps highlighted (place × category with
  no one).

## Blocked on

Real people and room data from the user. Build and test against the `_example` CSVs first.
