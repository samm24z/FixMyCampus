# Review 1 Verification

Verification date: 2026-09-27

Environment: Docker PostgreSQL/pgvector, FastAPI backend, seeded development accounts, and Vite frontend at `http://localhost:5173`.

Test ticket: `TICK-2026-0005` (`Review 1 role workflow complaint`)

## Complete Role Workflow

| Step | Result | Evidence |
| --- | --- | --- |
| 1. Login as STUDENT | PASS | Student demo account logged in through the browser and redirected to `/dashboard`. |
| 2. Create a complaint | PASS | Complaint form submitted through `/tickets/new`. |
| 3. Verify generated ticket number | PASS | Backend/frontend generated `TICK-2026-0005`. |
| 4. Ticket appears in student list | PASS | `/tickets` showed the new ticket with status `NEW`. |
| 5. Student logout | PASS | Navbar sign-out returned to `/login`. |
| 6. Login as COORDINATOR | PASS | Coordinator demo account redirected to `/staff`. |
| 7. Ticket appears in coordinator queue | PASS | Coordinator queue displayed `TICK-2026-0005` for triage. |
| 8. Assign department/staff | PASS | Coordinator selected `IT Department` and `Demo Staff`; detail metadata showed both. |
| 9. Change status to ASSIGNED | PASS | Coordinator control changed the ticket to `ASSIGNED`. |
| 10. Coordinator logout | PASS | Navbar sign-out returned to `/login`. |
| 11. Login as STAFF | PASS | Staff demo account redirected to `/staff`. |
| 12. Assigned ticket appears | PASS | Staff queue displayed `TICK-2026-0005` with `ASSIGNED`. |
| 13. Change status to IN_PROGRESS | PASS | Staff status control updated the ticket to `IN_PROGRESS`. |
| 14. Add staff comment | PASS | Comment appeared in the ticket detail: `Staff inspected the network equipment and started corrective work.` |
| 15. Change status to RESOLVED | PASS | Staff status control updated the ticket to `RESOLVED`. |
| 16. Staff logout | PASS | Navbar sign-out returned to `/login`. |
| 17. Login as STUDENT | PASS | Student demo account logged in again. |
| 18. Verify updated status/timeline | PASS | Student saw `RESOLVED`, IT Department, Demo Staff, the staff comment, and the accumulated timeline. |
| 19. Add feedback if implemented | N/A | Feedback API/UI is not implemented in Review 1; no fake feedback was added. |
| 20. Reopen ticket | PASS | Student used `Request Reopen` on the resolved ticket. |
| 21. Verify REOPENED status | PASS | Detail page displayed `REOPENED`. |
| 22. Verify complete timeline | PASS | Final timeline is `NEW -> ASSIGNED -> IN_PROGRESS -> RESOLVED -> REOPENED`. |

## Authorization Tests

| Check | Result | Evidence |
| --- | --- | --- |
| Student cannot access another user's ticket | PASS | Student request for a Faculty-owned temporary ticket returned `403`, validating ownership enforcement. The temporary record was removed after verification. The seeded database has one Student account, so a Faculty-owned ticket was used as the cross-user fixture. |
| Student cannot assign tickets | PASS | Student assignment request returned `403`. |
| Student cannot change staff-only statuses | PASS | Student `PATCH` status request to `IN_PROGRESS` returned `403`. |
| Staff cannot access admin functionality | PASS | Staff request to the protected admin check returned `403`; the frontend only exposes staff routes for STAFF. |
| Coordinator can assign tickets | PASS | Browser coordinator controls successfully assigned IT Department and Demo Staff. |
| Admin can view overall ticket data | PASS | Browser admin overview displayed all 5 current tickets and aggregate counts. |

## Final Database State

The database contains the four deterministic demo tickets plus the one workflow ticket used for this verification:

- `TICK-2026-0005`: `REOPENED`
- `TICK-2026-0101`: `NEW`
- `TICK-2026-0102`: `IN_PROGRESS`
- `TICK-2026-0103`: `RESOLVED`
- `TICK-2026-0104`: `REOPENED`

The temporary authorization-test ticket was deleted. The final workflow ticket has one staff comment and five status-history entries. No AI predictions, embeddings, or fake feedback were created.

## Bugs Found And Fixed

1. **Coordinator queue omitted unassigned tickets.** New tickets had no confirmed department, so the coordinator queue returned zero records. Coordinator visibility now includes unassigned tickets while preserving department scoping for assigned tickets.
2. **Coordinator demo account lost access after IT assignment.** The seeded coordinator was in General Administration. Development seed data now places the coordinator in IT, matching the Review-1 triage workflow.
3. **Assignment duplicated the `ASSIGNED` timeline transition.** The coordinator UI updated status and then called assignment, which recorded `ASSIGNED` twice. Assignment now records a status history row only when the status actually changes.
4. **Department assignment was implicit.** Coordinator controls now load active departments and require an explicit department selection when assigning staff.

## Validation Commands

- `docker compose run --rm backend pytest -q`: **14 passed**
- `npm test -- --run`: passed previously and remained unchanged by the final backend-only workflow fixes
- `npm run build`: passed previously; the department-control frontend change was build-verified during implementation
- Final database query: workflow timeline and statuses verified
