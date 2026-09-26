# Database Guide

FixMyCampus uses PostgreSQL 16 with the `pgvector` extension, SQLAlchemy 2 async sessions, and Alembic migrations. The migration and seed mechanism use the existing models and `backend/app/core/database.py`; no parallel database layer was added.

## ER/Domain Overview

`users` report and work on `tickets`. `departments` own categories and SLA rules and may contain users. Tickets may reference suggested/confirmed departments, a creator, and an assignee. Ticket child tables store comments, attachments, status history, assignments, feedback, duplicates, and notifications. `audit_logs` record user-linked entity changes. `knowledge_documents` contain `knowledge_chunks` for the future RAG layer; embeddings are nullable `vector(384)` columns and are not populated by this phase.

## Tables

| Table | Purpose |
| --- | --- |
| `roles` | Role reference records. |
| `users` | User accounts and role/department assignment. |
| `departments` | Campus operational departments. |
| `categories` | Ticket categories and default departments. |
| `tickets` | Core grievance records and optional 384-dimensional embedding. |
| `ticket_comments` | Public/internal ticket comments. |
| `ticket_attachments` | Uploaded ticket file metadata. |
| `ticket_status_history` | Ticket status transitions. |
| `ticket_assignments` | Assignment history. |
| `ticket_feedback` | One feedback record per ticket. |
| `ticket_duplicates` | Candidate duplicate links and verification state. |
| `sla_rules` | Category/priority resolution and escalation targets. |
| `notifications` | In-app notification records. |
| `audit_logs` | Entity change audit records. |
| `knowledge_documents` | Approved policy document metadata. |
| `knowledge_chunks` | Document chunks and optional vector embeddings. |

## Migration Commands

From `backend/` with the Python environment configured:

```powershell
alembic upgrade head
alembic current
alembic downgrade base
```

The initial migration enables `vector`, creates all current model tables, adds UUID/JSONB/timestamp/vector columns, foreign keys, indexes, and declared unique constraints.

## Seed Commands

From `backend/`:

```powershell
python scripts/seed_database.py
python scripts/seed_database.py --reset
```

The script uses stable UUIDs. A plain seed refuses to run when reference data already exists, preventing accidental duplicates. `--reset` refuses to run when operational tickets exist because the current model intentionally cascades user deletion to tickets. Use it only on a disposable development database; reset a full disposable schema with `alembic downgrade base` followed by `alembic upgrade head` when required.

Development demo users are:

| Role | Email | Password |
| --- | --- | --- |
| Student | `student@fixmycampus.dev` | `FixMyCampus-Dev-2026!` |
| Faculty | `faculty@fixmycampus.dev` | `FixMyCampus-Dev-2026!` |
| Staff | `staff@fixmycampus.dev` | `FixMyCampus-Dev-2026!` |
| Coordinator | `coordinator@fixmycampus.dev` | `FixMyCampus-Dev-2026!` |
| Admin | `admin@fixmycampus.dev` | `FixMyCampus-Dev-2026!` |

These credentials are local development-only and are not authentication functionality.

## Review-1 Demo Dataset

After the reference seed is present, replace only the browser-validation tickets with the deterministic synthetic demonstration dataset:

```powershell
Set-Location backend
python scripts/seed_demo_data.py
```

The command removes only validation tickets `TICK-2026-0001` and `TICK-2026-0002`, including their dependent records, and creates:

| Ticket | Status | Category |
| --- | --- | --- |
| `TICK-2026-0101` WiFi not working in C Block | `NEW` | IT / Network |
| `TICK-2026-0102` Projector not working in C-204 | `IN_PROGRESS` | Classroom Equipment |
| `TICK-2026-0103` Water leakage near laboratory | `RESOLVED` | Water / Plumbing |
| `TICK-2026-0104` Classroom fan not working | `REOPENED` | Electrical |

The demo command is idempotent, changes no schema or application code, and leaves AI fields and embeddings empty. All records are synthetic development data.

## Local Database Setup

From the repository root:

```powershell
Copy-Item .env.example .env
docker compose up -d db
docker compose exec db pg_isready -U postgres -d fixmycampus_db
Set-Location backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
python scripts/seed_database.py --reset
pytest -q
```

The backend application health check uses the same configured async database URL and executes `SELECT 1`; it does not create tables automatically.