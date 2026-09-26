# Current Project State

Audit date: 2026-09-27

This audit records repository evidence only. `PROJECT_ARCHITECTURE.md` is treated as a target specification, not proof that a feature exists.

## Detected Architecture

| Area | State | Evidence |
| --- | --- | --- |
| Frontend | COMPLETE (Review-1 workflows) | React 18, TypeScript, Vite, Tailwind CSS, centralized Axios client, auth state, protected routes, and live ticket screens are working. `npm test` and `npm run build` pass. |
| Backend | PARTIAL (Review-1 workflows) | FastAPI, Pydantic, SQLAlchemy async, Alembic, authentication/RBAC, and the minimal ticket routes required by Review 1 are working. Advanced ticket services remain deferred. |
| Database target | COMPLETE (Review-1 foundation) | PostgreSQL plus `pgvector/pgvector:pg16` is running; revision `20260927_0001` applied successfully; all 16 domain tables and `vector(384)` columns were verified. |
| AI target | PARTIAL | Interfaces, schemas, and deterministic mock implementations exist. No BERT, SentenceTransformer, vector search service, or RAG pipeline is wired into FastAPI. |
| Notifications target | MISSING | Notification model/schema exists, but no email, SMS, dispatch service, or API route exists. |

## Completed Features

| Feature | Status | Evidence |
| --- | --- | --- |
| Project scaffolding and configuration | COMPLETE | Monorepo layout, Python/Node manifests, Vite/Tailwind configuration, Docker files, `.env.example`, and setup documentation exist. |
| Frontend routing and presentational shell | COMPLETE | `frontend/src/router.tsx` registers the listed pages and `AppLayout` provides navbar/footer/layout. This is presentation-level completion only. |
| FastAPI application shell | COMPLETE | `backend/app/main.py` creates the app, configures CORS, OpenAPI URLs, root metadata, and health routers. |
| Health endpoint implementation | COMPLETE | `GET /health` and `GET /api/v1/health` are implemented and covered by source tests. Database status is checked through `SELECT 1` when dependencies/database are available. |
| AI interface contracts and mocks | COMPLETE | `ai/interfaces.py`, `ai/schemas.py`, and `ai/mock_service.py` define/test classifier, deduplication, priority, and RAG contracts. These are offline mocks, not production AI. |
| Frontend build and smoke test | COMPLETE | `npm run build` passed; the single Vitest smoke test passed. |

## Partially Implemented Features

| Feature | Status | Evidence |
| --- | --- | --- |
| Database domain layer | COMPLETE (Review-1 foundation) | The initial migration creates all current model tables, constraints, indexes, JSONB/vector columns, and the pgvector extension. Deterministic seed/reset is implemented and verified. |
| Authentication foundation | COMPLETE (Review-1) | Register, login, refresh, current-user resolution, bcrypt password hashing, access/refresh JWT expiry/type claims, and protected profile access are implemented and tested. |
| RBAC foundation | COMPLETE (Review-1 foundation) | Reusable `require_role(...)` server-side dependency and protected admin-check route are implemented and tested for wrong/correct roles. Domain ticket authorization remains deferred with ticket APIs. |
| Ticket domain foundation | PARTIAL (Review-1) | Minimal authenticated create/list/detail/comment/reopen/status/assignment routes now use the existing models and database session. Advanced lifecycle, attachments, feedback, and notifications remain deferred. |
| Frontend ticket experience | COMPLETE (Review-1) | Dashboard, complaint creation, list/search, detail, comments, reopen, status, and assignment controls use the centralized API client. |
| Staff/admin UI | PARTIAL (Review-1) | Staff queue, status updates, coordinator assignment/triage controls, and admin ticket overview are connected; broader administration remains deferred. |
| AI capability | PARTIAL | Keyword mock classification/priority and zero-vector/no-duplicate mock behavior are tested. Production model loading/inference is absent. |
| RAG capability | PARTIAL | RAG schemas and a canned mock answer/citation exist; policy documents are not present and no retrieval, indexing, LLM, or endpoint is wired. |

## Missing Features

| Feature | Status |
| --- | --- |
| Auth endpoints (`register`, `login`, `refresh`, `me`) and token validation | COMPLETE | Implemented under `/api/v1/auth` with access and stateless refresh JWTs. |
| Backend RBAC and ownership checks | PARTIAL | Role dependency and admin protection are implemented; ownership checks await ticket APIs. |
| User, department, category, ticket, comment, attachment, assignment, feedback, duplicate, SLA, notification, knowledge, analytics, and audit APIs | PARTIAL | Review-1 ticket create/list/detail/comment/assignment/status routes exist; the other domain APIs remain deferred. |
| Ticket creation, persistence, numbering, lifecycle state machine, resolution, reopen, and feedback workflows | PARTIAL | Creation, numbering, persistence, comments, reopen, and basic status updates work; full lifecycle and feedback are deferred. |
| Coordinator triage decision/override workflow and human review audit integration | MISSING |
| Transformer classifier and department recommendation | MISSING |
| Sentence embeddings and pgvector similarity duplicate detection | MISSING |
| Production priority/SLA engine | MISSING |
| RAG document ingestion, chunking, retrieval, grounded LLM responses, and citations | MISSING |
| Email/SMS notifications and in-app notification workflow | MISSING |
| Analytics aggregation and SLA monitoring | MISSING |
| Database migrations and synthetic seed/demo records | COMPLETE | Alembic revision `20260927_0001` and deterministic seed/reset script are implemented and verified. |
| Frontend API client workflows, authentication state, protected routes, ticket forms, staff actions, admin actions, and live assistant input | PARTIAL | Auth and ticket workflows are connected; assistant remains intentionally disabled because RAG is not implemented. |

## Broken Features

| Feature | Status | Evidence |
| --- | --- | --- |
| Backend host startup in the audited environment | BROKEN in environment | Host Python still lacks the backend dependencies; the containerized backend starts successfully and serves auth/health routes. |
| Database connectivity | COMPLETE | Docker PostgreSQL is healthy; the application `check_db_health()` returned `True` and live `/api/v1/health` returned `database: connected`. |
| Backend container runtime | COMPLETE | Backend image rebuilt successfully and the Uvicorn service started on port 8000. |
| Frontend authentication forms | COMPLETE | Login and registration call the backend, store tokens, load the current user, handle errors, and redirect by role. |
| Frontend policy assistant interaction | BROKEN as user workflow | The displayed conversation is hard-coded; question input and send button are disabled. |
| Frontend ticket data | COMPLETE (Review-1) | Dashboard/list/detail/create/comment/reopen/status/assignment workflows use live backend data. |
| Health AI status | BROKEN as an availability signal | `ai_subsystem` is always returned as `ready`; no AI service health check is performed. |
| Exception handler registration | BROKEN/incomplete | `register_exception_handlers` exists but is never called from `main.py`. |
| Production security configuration | BROKEN/incomplete | Default development secret and database password are present in `.env.example` and `.env`; they must not be used for deployment. |

## Existing API Endpoints

Implemented routes:

| Method | Path | Status |
| --- | --- | --- |
| GET | `/` | COMPLETE; returns API metadata. |
| GET | `/health` | COMPLETE; returns health payload and attempts database check. |
| GET | `/api/v1/health` | COMPLETE; same health handler under the versioned router. |
| POST | `/api/v1/auth/register` | COMPLETE; public registration is limited to student/faculty roles. |
| POST | `/api/v1/auth/login` | COMPLETE; returns access and refresh JWTs. |
| POST | `/api/v1/auth/refresh` | COMPLETE; exchanges a valid refresh JWT for a new token pair. |
| GET | `/api/v1/auth/me` | COMPLETE; requires a valid access JWT. |
| GET | `/api/v1/auth/directory/staff` | COMPLETE (internal); coordinator/admin staff assignment directory. |
| GET | `/api/v1/tickets/summary` | COMPLETE; authenticated dashboard counts and recent tickets. |
| GET | `/api/v1/tickets` | COMPLETE; role-scoped live ticket list with search. |
| POST | `/api/v1/tickets` | COMPLETE; authenticated complaint creation. |
| GET | `/api/v1/tickets/{ticket_ref}` | COMPLETE; role-scoped detail, comments, assignments, and history. |
| POST | `/api/v1/tickets/{ticket_ref}/comments` | COMPLETE; permitted reporter/staff/coordinator/admin comments. |
| POST | `/api/v1/tickets/{ticket_ref}/reopen` | COMPLETE; reporter-only reopen for resolved/closed tickets. |
| PATCH | `/api/v1/tickets/{ticket_ref}` | COMPLETE (basic); staff status updates and coordinator/admin triage/status changes. |
| POST | `/api/v1/tickets/{ticket_ref}/assign` | COMPLETE (basic); coordinator/admin assignment. |

The architecture document lists additional endpoint plans beyond this Review-1 slice; AI/RAG, notification, analytics, and advanced ticket endpoints remain unregistered.

## Existing Database Tables

The ORM declares these table names, and the initial migration created and verified them:

`roles`, `users`, `departments`, `categories`, `tickets`, `ticket_comments`, `ticket_attachments`, `ticket_status_history`, `ticket_assignments`, `ticket_feedback`, `ticket_duplicates`, `sla_rules`, `notifications`, `audit_logs`, `knowledge_documents`, and `knowledge_chunks`.

The ticket and knowledge chunk models declare `VectorType(384)`, which maps to `vector(384)` on PostgreSQL. The `vector` extension, model indexes, foreign keys, and unique constraints were verified after migration.

## Existing Frontend Routes

| Route | Component | Status |
| --- | --- | --- |
| `/` | HomePage | COMPLETE as static landing/status page; only health polling is live. |
| `/login` | LoginPage | COMPLETE; live login, token storage, errors, and role redirect. |
| `/register` | RegisterPage | COMPLETE; live student/faculty registration and validation. |
| `/dashboard` | DashboardPage | COMPLETE (Review-1); live ticket totals and recent tickets. |
| `/tickets` | TicketsPage | COMPLETE (Review-1); live list, search, loading/error/empty states. |
| `/tickets/new` | CreateComplaintPage | COMPLETE (Review-1); live complaint creation. |
| `/tickets/:id` | TicketDetailPage | COMPLETE (Review-1); live detail/comments/status/assignment/reopen controls. |
| `/admin` | AdminPage | PARTIAL (Review-1); live ticket overview. |
| `/staff` | StaffPage | PARTIAL (Review-1); live queue and detail actions. |
| `/assistant` | AssistantPage | PARTIAL/BROKEN workflow; canned messages and disabled input. |
| `*` | NotFoundPage | COMPLETE as a fallback page. |

## Existing AI Components

| Component | Status | Evidence |
| --- | --- | --- |
| `BaseClassifierService` | COMPLETE (contract) | Async classification interface. |
| `MockClassifierService` | COMPLETE (mock) | Keyword-based categories and department suggestions. |
| `BaseDeduplicationService` | COMPLETE (contract) | Embedding and duplicate-search interface. |
| `MockDeduplicationService` | COMPLETE (mock only) | Returns 384 zeros and no candidates; it does not perform semantic detection. |
| `MockPriorityService` | COMPLETE (mock) | Keyword-based priority and SLA recommendations. |
| `MockRAGService` | COMPLETE (mock only) | Returns a canned answer and citation; no document retrieval occurs. |
| Transformer classifier | MISSING | Only model name configuration exists. |
| Sentence embeddings/pgvector search | MISSING | Only model/type configuration and ORM columns exist. |
| RAG ingestion/retrieval/LLM | MISSING | No implementation or policy source files exist. |

## Existing Tests

| Test area | Status | Evidence |
| --- | --- | --- |
| Backend health tests | COMPLETE | `backend/tests/test_health.py` and the database metadata tests pass in the backend container. |
| Backend fixture | PARTIAL | `backend/tests/conftest.py` provides an ASGI client but imports the app/database stack. It has no database fixture. |
| AI mock tests | PARTIAL | `tests/test_ai_interfaces.py` covers four mock behaviors; it does not test production AI or API integration. |
| Frontend tests | COMPLETE (smoke only) | One Vitest assertion passes; no component, route, API, accessibility, or end-to-end tests exist. |
| Migration/integration/security tests | PARTIAL | Database metadata/migration and auth/RBAC tests pass; live ticket flow was manually verified, while dedicated ticket ownership tests remain. |

## Current Run Commands

Declared commands:

```text
docker compose up --build
cd backend; pip install -r requirements.txt; uvicorn app.main:app --reload --port 8000
cd frontend; npm install; npm run dev
pytest -q
cd frontend; npm test -- --run
cd frontend; npm run build
```

Audit results:

- `npm test -- --run`: PASS, 1 test file and 1 test after live workflow wiring.
- `npm run build`: PASS; TypeScript compilation and Vite production build succeeded after live workflow wiring.
- `docker compose config`: PASS.
- `docker compose run --rm backend pytest -q`: PASS, 14 tests including authentication/RBAC.
- `docker run ... pytest -q tests`: PASS, 4 AI interface tests.
- `npm test -- --run`: PASS, 1 frontend smoke test.
- `npm run build`: PASS; TypeScript compilation and Vite production build succeeded.
- `docker compose config`: PASS.
- `alembic upgrade head`: PASS; revision `20260927_0001`.
- `alembic downgrade base` then `upgrade head`: PASS.
- Seed reset: PASS; 5 roles, 7 departments, 8 categories, 5 users, 32 SLA rules.
- PostgreSQL/pgvector: PASS; database healthy, extension and all 16 tables verified.
- Backend health: PASS; `check_db_health()` returned `True`, and live `/api/v1/health` returned `database: connected`.
- Host-only `pytest`/backend import remain unavailable until local dependencies are installed; Docker validation is green.
- Live ticket workflow: PASS; student created `TICK-2026-0001`, fetched it, added a comment, and dashboard totals reflected the ticket.
- Live admin workflow: PASS; admin login, `/me`, refresh, and server-side admin role check passed.

Environment variables are defined in `.env.example` and `.env`: project/server settings, API prefix, JWT secret/expiry, PostgreSQL connection values, CORS origins, Vite API base URL, embedding/classifier model names, similarity threshold, and optional OpenAI key. The checked-in values are development placeholders and are not suitable for production. `email-validator` is now declared because existing Pydantic `EmailStr` schemas require it.

## Recommended Next Phase

**Next phase: complete the ticket lifecycle and ownership-aware authorization.**

1. Add dedicated backend ticket integration tests for ownership, department scope, and staff/coordinator actions.
2. Complete status transition rules, feedback, attachments, and notification hooks.
3. Add frontend refresh-token retry and broader role-specific workflow coverage.
4. Implement AI/RAG only after the core lifecycle is stable.

The database, authentication/RBAC, and Review-1 frontend ticket workflows are executable and reproducible; AI/RAG and advanced ticket capabilities remain intentionally deferred.