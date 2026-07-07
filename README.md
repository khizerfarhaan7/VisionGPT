# VisionGPT (SaaS Application Initializer)

VisionGPT is a production-ready AI SaaS application built with Next.js 15, FastAPI, and PostgreSQL.

This workspace represents the base initialized layout with a modular code architecture, environment configuration, and containerized dev environments.

---

## 1. Project Directory Structure

```text
MAJOR PROJECT/
├── backend/                  # FastAPI Backend (Python 3.12)
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── endpoints/
│   │   │       │   ├── __init__.py
│   │   │       │   └── health.py  # Health check endpoint
│   │   │       ├── __init__.py
│   │   │       └── api.py         # Versioned Router aggregator
│   │   │   └── __init__.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py          # Pydantic Settings
│   │   │   └── database.py        # SQLAlchemy & asyncpg setup
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   └── health.py          # Pydantic Schema definitions
│   │   ├── __init__.py
│   │   └── main.py                # App lifecycle, CORS middleware
│   ├── Dockerfile                 # Multi-stage image build
│   └── requirements.txt           # Pinned python packages
├── frontend/                 # Next.js 15 Frontend
│   ├── src/
│   │   ├── app/
│   │   │   ├── globals.css        # Tailwind V4 + shadcn styles
│   │   │   ├── layout.tsx
│   │   │   └── page.tsx
│   │   ├── components/
│   │   │   └── ui/                # shadcn components (e.g. Button)
│   │   └── lib/
│   │       └── utils.ts           # Helper styles utils
│   ├── components.json            # shadcn/ui configuration
│   ├── Dockerfile                 # Standalone production container build
│   ├── next.config.ts             # Output standalone option enabled
│   ├── package.json
│   └── tsconfig.json
├── database/                 # Directory reserved for SQL / Alembic migrations
├── docs/                     # Architectural documents & design assets
├── uploads/                  # Local filesystem storage placeholder for uploads
├── .env                      # Loaded environment config
├── .env.example              # Config template
└── docker-compose.yml        # Orchestrates db, backend, and frontend
```

---

## 2. Environment Variables Setup

Copy `.env.example` to `.env` (already done by the initialization script):
```bash
cp .env.example .env
```

Review files:
- **`BACKEND_PORT`**: Port mapping for the Python API (Default: `8000`).
- **`FRONTEND_PORT`**: Port mapping for Next.js (Default: `3000`).
- **`POSTGRES_SERVER`**: Use `db` when running under docker-compose, and `localhost` when executing locally.

---

## 3. How to Run

### Option A: Run via Docker (Recommended)
This spins up PostgreSQL, the FastAPI backend (with auto-reload enabled), and the Next.js frontend in separate containers.

```bash
docker compose up --build
```

### Option B: Run Services Locally

#### Run Backend Locally
1. Navigate to the backend directory and set up a virtual environment:
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run uvicorn server (make sure Postgres is running locally and credentials match `.env`):
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

#### Run Frontend Locally
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install packages:
   ```bash
   npm install
   ```
3. Boot Next.js in development mode:
   ```bash
   npm run dev
   ```

---

## 4. Expected Initialization Output

- **Frontend Landing Page**: Accessing [http://localhost:3000](http://localhost:3000) should show the Next.js home screen.
- **Backend API Root**: Accessing [http://localhost:8000](http://localhost:8000) should return:
  ```json
  {
    "project": "VisionGPT",
    "docs_url": "/docs",
    "api_v1_url": "/api/v1"
  }
  ```
- **Backend Health Check**: Accessing [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health) verifies API integrity and PostgreSQL connection availability:
  ```json
  {
    "status": "healthy",
    "environment": "development",
    "database": "healthy",
    "version": "0.1.0"
  }
  ```
