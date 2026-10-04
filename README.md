# FixMyCampus AI

> **FixMyCampus AI: An Intelligent Campus Grievance Classification, Deduplication and Resolution Platform**  
> *Final-Year Engineering Project &bull; Full-Stack + Generative AI &bull; MVSR Engineering College*

---

## 🌟 Overview

**FixMyCampus AI** is a production-style campus grievance management platform where students, faculty, and staff can report infrastructure, IT, sanitation, electrical, plumbing, civil maintenance, and academic-facility issues. Every complaint becomes a traceable ticket that can be assigned, triaged, resolved, reopened, and audited.

The platform integrates applied Generative AI and Machine Learning:
1. **Intelligent Text Classification**: Automatically predicts the grievance category and suggests responsible departments.
2. **pgvector Semantic Deduplication**: Generates 384-dimensional dense embeddings to detect existing duplicate complaints in real time.
3. **Dynamic Urgency & Priority Scoring**: Analyzes severity keywords and context to recommend SLA targets.
4. **Campus Policy RAG Assistant**: A grounded retrieval-augmented generation assistant providing accurate answers with source citations from approved campus handbooks.
5. **Human-in-the-Loop Governance**: AI provides suggestions only; authorized staff verify and override recommendations with complete audit trails.

---

## 🏗️ Architecture & Monorepo Layout

```
fixmycampus-ai/
├── frontend/             # React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui
├── backend/              # Python 3.12, FastAPI, SQLAlchemy 2.0 Async, Alembic
├── ai/                   # Modular AI services (Classifiers, Embeddings, RAG)
├── data/                 # Synthetic complaint seed datasets & approved policy docs
├── docs/                 # System architecture & developer guides
├── tests/                # Top-level smoke tests & AI interface tests
├── docker/               # Dockerfiles for backend and frontend services
├── .env.example          # Environment variable template
├── .gitignore            # Git exclusion rules
├── README.md             # Project documentation & execution guide
├── PROJECT_ARCHITECTURE.md # Full technical specification
└── docker-compose.yml    # Development multi-container orchestration
```

For detailed architecture diagrams, database ERDs, API boundaries, and security models, see [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md).

---

## 🚀 Quick Start Guide

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) to host the database, backend and frontend so the app works from any device.

### Option 1: Docker Compose (Recommended)

Run the entire stack (PostgreSQL with `pgvector`, FastAPI backend, and React frontend) with a single command:

```bash
# 1. Clone the repository and configure environment variables
cp .env.example .env

# 2. Build and launch containers
docker compose up --build
```

- **Frontend App**: [http://localhost:5173](http://localhost:5173)
- **Backend API & Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **API Health Endpoint**: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)
- **PostgreSQL + pgvector**: `localhost:5432`

---

### Option 2: Local Development Setup

#### 1. Database (PostgreSQL with pgvector)
```bash
docker compose up -d db
```

#### 2. Backend (FastAPI)
```bash
cd backend

# Create and activate Python virtual environment
python -m venv .venv
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On macOS/Linux:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --port 8000
```

#### 3. Frontend (React + Vite)
```bash
cd frontend

# Install node dependencies
npm install

# Start Vite dev server
npm run dev
```

---

## 🧪 Running Tests

### Backend Unit & Integration Tests:
```bash
cd backend
pytest -v
```

### Top-level AI Interface Tests:
```bash
pytest tests/ -v
```

### Frontend Tests:
```bash
cd frontend
npm test
```

---

## 🛣️ Project Phases Roadmap

- [x] **Phase 0: Project Foundation**
- [x] **Phase 1: Database Models, Migrations & Synthetic Seed Data**
- [x] **Phase 2: Authentication, Security & RBAC Engine**
- [x] **Phase 3: Core Complaint Lifecycle & State Machine** *(attachments, feedback, notifications pending)*
- [ ] **Phase 4: AI Classifier, Priority Engine & Deduplication**
- [ ] **Phase 5: Coordinator Triage Workbench & Override System**
- [ ] **Phase 6: Policy RAG Assistant with Grounded Citations**
- [ ] **Phase 7: Notification & Feedback Subsystem**
- [ ] **Phase 8: Modern Frontend Engineering (Tailwind / shadcn/ui)**
- [ ] **Phase 9: Executive Analytics, SLA Tracker & Audit Logs**
- [ ] **Phase 10: End-to-End Testing & Production Readiness**
