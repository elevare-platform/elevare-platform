# Elevare Platform

Recruitment platform for Elevare Human Solutions Ltd.

**Stack:** FastAPI · React · PostgreSQL · Cloudflare R2 · Docker · Nginx

---

## Local Development Setup

### Prerequisites
- Python 3.11+
- Docker + Docker Compose
- Node 18+ (frontend — Phase 7)

### First-time setup

1. Clone the repo
2. Set up Git identity for this repo:
```bash
   git config user.name "Elevare Dev"
   git config user.email "dev@elevarehuman.com"
```
3. Copy environment template:
```bash
   cp .env.example backend/.env
   # Fill in values in backend/.env
```

### Running locally

```bash
docker-compose up --build
```

API available at: http://localhost:8000  
Health check: http://localhost:8000/health  
API docs (dev only): http://localhost:8000/docs

### Running tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

### Running linter

```bash
cd backend
ruff check .
```

---

## Project Structure
elevare-platform/
├── .github/workflows/   # CI pipeline
├── backend/
│   ├── app/
│   │   ├── core/        # config, database, logging
│   │   ├── modules/     # feature modules (auth, jobs, etc.)
│   │   └── main.py
│   ├── alembic/         # database migrations
│   └── tests/
├── frontend/            # React app (Phase 7)
└── docker-compose.yml

---

## Phase Status

| Phase | Name | Status |
|-------|------|--------|
| 1 | Foundation & Project Skeleton | ✅ Complete |
| 2 | Authentication & User System | 🔜 Next |
| 3 | Job Listings + Minimal Dev UI | ⏳ Pending |
| 4 | Candidate Profiles & CV Upload | ⏳ Pending |
| 5 | Job Applications | ⏳ Pending |
| 6 | Admin Dashboard API | ⏳ Pending |
| 6.5 | Early AI Signal | ⏳ Pending |
| 7 | Full Frontend | ⏳ Pending |
| 8 | Deployment & Production Hardening | ⏳ Pending |