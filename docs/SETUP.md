# FixMyCampus AI - Setup & Developer Guide

## 1. Prerequisites
- **Node.js**: v20+ or v22+
- **Python**: v3.12+
- **Docker & Docker Compose**: (Recommended for PostgreSQL with `pgvector`)
- **Git**

---

## 2. Quick Start with Docker (Recommended)

To launch the entire platform (PostgreSQL with pgvector, FastAPI Backend, and React Frontend) with a single command:

```bash
# 1. Clone the repository and copy environment variables
cp .env.example .env

# 2. Build and start all services
docker compose up --build
```

- **Frontend Application**: `http://localhost:5173`
- **Backend API & Swagger Docs**: `http://localhost:8000/docs`
- **API Health Check**: `http://localhost:8000/api/v1/health`
- **PostgreSQL Database**: `localhost:5432`

---

## 3. Local Development (Manual Setup)

### 3.1 Start Database with pgvector
```bash
docker compose up -d db
```

### 3.2 Backend Setup
```bash
# Navigate to backend directory
cd backend

# Create and activate a virtual environment
python -m venv .venv
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On Linux / macOS:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the FastAPI server
uvicorn app.main:app --reload --port 8000
```

### 3.3 Frontend Setup
```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```

---

## 4. Running Tests

### Backend Tests:
```bash
cd backend
pytest -v
```

### Frontend Tests:
```bash
cd frontend
npm test
```
