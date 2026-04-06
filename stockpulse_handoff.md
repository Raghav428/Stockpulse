# StockPulse — Project Handoff Document v2
**Last Updated:** 26 March 2026  
**Purpose:** Complete context for any engineer, mentor, or LLM continuing this project

---

## 1. WHO IS THE LEARNER?

- Decent Python knowledge (sync FastAPI, uv package manager, basic PostgreSQL/SQL)
- Comfortable with Linux CLI (navigate, edit files, processes)
- Has used docker-compose before, heard of Kubernetes but never used it
- 4+ hrs/day available
- Goal: proficiency + interview-level clarity across the full stack in 6 weeks
- Preferred style: **Socratic/guided** — ask questions, let the learner reason to answers before giving them. Only explain directly when they say "no idea" twice or the concept is not guessable.

---

## 2. THE PROJECT: StockPulse Platform

A real-time stock data ingestion, storage, querying, and alerting platform. ML/prediction/risk analysis will be plugged in later — the current focus is the infrastructure and backend engineering.

### Why this project justifies the stack:
| Technology | Justification |
|---|---|
| Cassandra | Time-series tick data — write-heavy, append-only, massive volume, partition by (symbol, date) |
| PostgreSQL | User accounts, watchlists, alert configs — relational, ACID |
| Redis | Live intraday cache — derived from Kafka, no persistence needed |
| Kafka | Event buffer between ingestion and storage — decouples producers/consumers, handles backpressure |
| FastAPI (async) | I/O-heavy service — async prevents event loop blocking on DB/Redis calls |
| nginx | Reverse proxy, SSL termination, load balancing — single entry point |
| Docker | Containerization — reproducible, portable, environment-agnostic |
| Kubernetes | Orchestration of 8 independent services at scale |
| Ansible | Provision and configure AWS infrastructure as code |
| GitHub Actions | CI/CD — push → test → build → deploy |
| AWS | Cloud runtime environment |

---

## 3. ARCHITECTURE (DESIGNED FROM FIRST PRINCIPLES)

The learner designed this architecture themselves through Socratic questioning. Every component is justified.

```
Browser
  → nginx (SSL termination, reverse proxy, load balancing)
    → FastAPI service (async, handles HTTP + WebSocket)
      → Redis (live intraday data, derived cache)
      → Cassandra (historical tick data)
      → PostgreSQL (users, watchlists, alerts)

Ingestion Pipeline (runs independently):
  External API (Yahoo/NSE/BSE)
    → Ingestion Service (fetches + publishes)
      → Kafka (event buffer, source of truth for tick data)
        → Consumer Service (reads Kafka, writes to Redis + Cassandra)
```

### Key architectural decisions made:
- **Cassandra schema:** `PRIMARY KEY ((symbol, date), ts)` — partition by symbol+date, cluster by timestamp. Prevents unbounded partition growth, enables fast range queries.
- **Redis is stateless** — derived from Kafka, no volume needed. Kafka can rebuild it after restart.
- **Event-driven notifications** — ticks fire events, alert consumers react. No polling.
- **8 independent services:** PostgreSQL, Cassandra, Redis, Kafka, FastAPI, Consumer Service, Ingestion Service, nginx

### Data access patterns identified:
- Historical data: read-heavy, rarely changes, cache aggressively, refresh off-hours
- Live/intraday data: append-only, constantly changing, Redis cache updated per tick
- User data: relational, ACID, transactional

---

## 4. CURRENT STATE OF THE CODEBASE

### Project structure:
```
stockpulse/
├── .env                            # POSTGRES_PASSWORD (gitignored)
├── .gitignore                      # Ignores __pycache__, .venv, .env, setup_manual.txt
├── .python-version                 # Python 3.12
├── .vscode/
│   └── settings.json               # IDE config to hide __pycache__, .pyc, .pyo etc
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI entry point (lifespan, async sessions, routes)
│   ├── api/                        # Future API routers (empty)
│   ├── core/
│   │   └── database.py             # Async engine, session factory, Base, URLs
│   ├── crud/                       # Future DB query functions (empty)
│   ├── models/
│   │   └── models.py               # SQLAlchemy User model (id, email, created_at, hashed_pass)
│   └── schemas/
│       └── schema.py               # Pydantic Stock schema
├── migrations/
│   ├── env.py                      # Uses ALEMBIC_DATABASE_URL + Base metadata + models import
│   └── versions/
│       └── d6f77d76792d_create_users_table.py  # Creates Users table (id, email, created_at only)
├── Dockerfile                      # python:3.12-slim, uv, start.sh entrypoint
├── compose.yml                     # PostgreSQL + Redis + FastAPI
├── start.sh                        # Runs alembic upgrade head then uvicorn
├── alembic.ini
├── setup_manual.txt                # Developer notes for Docker commands
├── pyproject.toml
└── uv.lock
```

### What is fully working:
- Full Docker Compose stack: PostgreSQL + Redis + FastAPI boots cleanly from scratch
- PostgreSQL healthcheck — FastAPI waits for `service_healthy` before starting
- `start.sh` entrypoint — Alembic migrations run automatically on every container start
- `POSTGRES_DB: stockpulse` — database auto-created on first run via `POSTGRES_DB` env var
- `.env` secrets — `POSTGRES_PASSWORD` injected via Compose, gitignored, never hardcoded
- FastAPI `/health` — runs real `SELECT 1` against PostgreSQL via async session
- FastAPI `/stock/{symbol}` — validated path param (uppercase, 1-5 chars), returns dummy data
- Pydantic `Path()` validation — 422 before function runs on invalid input
- Alembic migrations — Users table created automatically on startup
- Async SQLAlchemy with `asyncpg` — connection pooling via `async_sessionmaker`
- `lifespan` pattern — `AsyncSessionLocal` stored on `app.state.db`, engine disposed on shutdown
- Layer caching in Docker builds — dependencies cached separately from code
- Volume persistence — `pgdata` survives container restarts
- Bind mount with `.venv` exclusion — local code changes reflect in container without rebuilds

### ⚠️ Known issues:
- **Auth dependencies mostly used now** — `argon2-cffi` and `pyjwt[crypto]` are in use, but `pydantic-settings` and `structlog` from `pyproject.toml` have not been implemented.
- Login route (`POST /api/v1/auth/login`) is missing and needs to be implemented.

### Key files (current exact state):

**`app/core/database.py`**
```python
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

Base = declarative_base()

pg_password = os.getenv("POSTGRES_PASSWORD")

if pg_password:
    DATABASE_URL = f"postgresql+asyncpg://postgres:{pg_password}@my_postgres:5432/stockpulse"
else:
    raise RuntimeError("POSTGRES_PASSWORD environment variable not set")

ALEMBIC_DATABASE_URL = f"postgresql://postgres:{pg_password}@my_postgres:5432/stockpulse"

engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

**`app/main.py`**
```python
from fastapi import FastAPI, Path, Request
from app.core.database import AsyncSessionLocal, engine
from contextlib import asynccontextmanager
from sqlalchemy import text

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = AsyncSessionLocal
    yield
    await engine.dispose()

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health(request: Request):
    async with request.app.state.db() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ok"}

@app.get("/stock/{symbol}")
async def stock(symbol: str = Path(min_length=1, max_length=5, pattern=r"^[A-Z]+$")):
    return {
        "symbol": symbol,
        "price": 3 * int(len(symbol)) + 2,
        "date_listed": "23/01/2003"
    }
```

**`app/models/models.py`**
```python
from app.core.database import Base
from sqlalchemy import Column, String, Integer, DateTime, Date, Boolean
from sqlalchemy.sql import func

class User(Base):
    __tablename__ = "Users"

    id = Column(Integer, primary_key=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=True)
    DOB = Column(Date, nullable=False)
    email = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
```

**`start.sh`**
```bash
#!/bin/bash
uv run alembic upgrade head
/app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**`Dockerfile`**
```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN pip install uv
COPY pyproject.toml uv.lock ./
RUN uv sync
COPY . .
CMD ["./start.sh"]
```

**`compose.yml`**
```yaml
services:
  my_postgres:
    image: postgres
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: stockpulse
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql
    healthcheck:
      test: ['CMD-SHELL', 'pg_isready -U postgres']
      interval: 5s
      timeout: 5s
      retries: 5

  my_redis:
    image: redis
    ports:
      - "6379:6379"

  fastapi:
    build: .
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - .:/app
      - /app/.venv
    ports:
      - "8000:8000"
    depends_on:
      my_postgres:
        condition: service_healthy

volumes:
  pgdata:
```

### Dependencies (`pyproject.toml`):
```
alembic, argon2-cffi, asyncpg, dotenv, fastapi, psycopg2-binary,
pydantic-settings, pyjwt[crypto], python-dotenv, sqlalchemy, structlog, uvicorn
```

---

## 5. CONCEPTS THE LEARNER HAS DEEPLY UNDERSTOOD

Learned through reasoning, not memorization:

- **Docker:** containers vs VMs, layers, layer caching, volumes, networking, DNS, port mapping
- **Docker Compose:** services, shared networks, healthchecks, depends_on, env vars, `.env` files
- **Container ephemerality:** stateful vs stateless services, which need volumes and why
- **Async FastAPI:** event loop, await points, why sync blocks, CPU-bound vs I/O-bound
- **Pydantic validation:** type hints, `Path()`, 422 vs 500, validation as a layer
- **Connection pooling:** why it exists, `async_sessionmaker`, borrow/return pattern
- **Alembic:** autogenerate, `env.py`, `target_metadata`, offline vs online mode, why migrations run in container not on host
- **PostgreSQL connection strings:** asyncpg vs psycopg2, why two URLs exist
- **lifespan pattern:** startup/shutdown hooks, `app.state` as shared storage across requests
- **async with:** context managers, guaranteed cleanup, connection leak prevention
- **Cassandra data modeling:** partition key, clustering key, query-driven design, partition sizing

---

## 6. TEACHING STYLE NOTES

- **Socratic first** — always ask the learner to reason before explaining
- **Build on prior reasoning** — reference things the learner already said/figured out
- **One concept at a time** — learner explicitly said "you're telling me to do too much at once"
- **Concrete over abstract** — analogies (hospital receptionist for nginx, library for connection pool) land well
- **Let them fail and debug** — the `inr` typo, the 500 error, the `engine=` keyword bug were all valuable learning moments
- **Don't give code until they've attempted it** — show skeleton, ask them to fill gaps
- **When they say "no idea" twice** — just explain directly, don't keep probing

---

## 7. 20-DAY PLAN (Day-by-Day)

### Day 1 
- [x] async with deep dive — context managers, guaranteed cleanup
- [x] Generate missing Alembic migration for User model updates
- [x] Introduce `Depends` pattern for DB sessions

### Day 2 — User CRUD + Pydantic Schemas
- [x] Create `UserCreate` and `UserResponse` Pydantic schemas
- [x] `POST /api/v1/auth/register` — create a user, write to PostgreSQL
- [x] `GET /api/v1/auth/users/{id}` — fetch user by ID
- [x] Understand SQLAlchemy models (DB layer) vs Pydantic schemas (API layer)
- [x] Understand why you never return a SQLAlchemy model directly from a route

### Day 3 — Password Hashing + Auth Setup
- [x] Hash passwords with `argon2-cffi` before storing
- [x] JWT token generation functions
- [ ] `POST /api/v1/auth/login` — verify credentials, return JWT token
- [ ] Understand JWT structure: header, payload, signature

### Day 4 — Protected Routes + Middleware
- Decode and verify JWT on protected routes
- Build a `get_current_user` dependency
- `GET /users/me` — returns current user from token
- Understand FastAPI middleware vs dependencies

### Day 5 — Watchlist Model + CRUD
- Design `Watchlist` and `WatchlistItem` models
- Migrations for new tables
- `POST /watchlists`, `GET /watchlists`, `POST /watchlists/{id}/stocks`, `DELETE`
- Foreign keys and relationships in SQLAlchemy

### Day 6 — nginx
- Add nginx container to compose
- Write `nginx.conf` — reverse proxy to FastAPI
- Understand `location` blocks, `proxy_pass`, `upstream`
- All traffic flows through nginx, not directly to FastAPI
- Test all existing endpoints work through nginx

### Day 7 — Review + Git + README
- Set up proper Git repo with meaningful commit history
- Write README with ASCII architecture diagram
- Full `docker compose down -v && docker compose up --build` from scratch — verify clean boot

### Day 8 — Cassandra Introduction
- Add Cassandra to compose
- Understand keyspaces, tables, partitions
- Connect from Python using `cassandra-driver`
- Create `tick_data` table: `PRIMARY KEY ((symbol, date), ts)`
- Insert and query dummy tick rows

### Day 9 — Cassandra + FastAPI Integration
- `GET /stocks/{symbol}/history?date=2026-03-25`
- Query Cassandra for tick data by symbol + date
- Handle "no data found" gracefully

### Day 10 — Kafka Introduction
- Add Kafka to compose
- Understand topics, partitions, producers, consumers, consumer groups
- Write a minimal producer and consumer in Python
- Verify end-to-end message flow

### Day 11 — Ingestion Service
- Build `ingestion/` as a separate Python service
- Fetch real tick data from `yfinance`
- Publish each tick as JSON to Kafka topic `ticks`
- Containerize and add to compose

### Day 12 — Consumer Service
- Build `consumer/` as a separate Python service
- Read from Kafka `ticks` topic
- Write to Redis (key: `tick:{symbol}`, value: latest price)
- Write to Cassandra (persistent storage)
- Containerize and add to compose

### Day 13 — FastAPI Live Data Endpoint
- `GET /stocks/{symbol}/live` — reads from Redis
- Async Redis client (`redis-py` async)
- Handle cache miss gracefully (fall back to Cassandra)
- Test full pipeline: yfinance → Kafka → consumer → Redis → FastAPI → browser

### Day 14 — WebSockets
- `WS /stocks/{symbol}/stream` — streams live prices to connected clients
- Understand WebSocket lifecycle: connect, send, receive, disconnect
- Consumer publishes to Redis pub/sub
- FastAPI WebSocket handler subscribes and pushes to browser

### Day 15 — AWS + Ansible Introduction
- Create AWS account, set up IAM user
- Understand VPCs, subnets, security groups, EC2
- Write first Ansible playbook — provision an EC2 instance
- SSH into it, verify it's alive
- Understand inventory files, hosts, roles

### Day 16 — Deploy Stack to AWS with Ansible
- Ansible playbook to install Docker on EC2
- Copy compose files to EC2 and start the stack remotely
- Configure security group to allow ports 80, 443, 8000
- Verify `/health` responds from the public IP

### Day 17 — Kubernetes Introduction
- Install `k3s` locally
- Understand Pod, Deployment, Service, ConfigMap, Secret, Ingress
- Translate PostgreSQL compose service into K8s manifests
- `kubectl apply`, `kubectl get pods`, `kubectl logs`

### Day 18 — Full Stack on Kubernetes
- Write K8s manifests for all services
- Understand Ingress vs LoadBalancer vs NodePort
- Deploy full stack to local k3s
- Verify health check passes through Ingress

### Day 19 — GitHub Actions CI/CD
- GitHub Actions workflow on push to `main`
- push → test → build image → push to registry → deploy to K8s
- Secrets management in GitHub Actions
- First fully automated deploy from `git push`

### Day 20 — Polish + LinkedIn Ready
- Comprehensive README with architecture diagram
- Clean up all TODO comments and dead code
- Full end-to-end test: register → login → watchlist → live price → history
- 3 interview talking points per technology written up

---

## 8. INTERVIEW TALKING POINTS ALREADY EARNED

- Why Cassandra for tick data vs PostgreSQL
- Cassandra partition key design and the partition growth problem
- Why async matters for I/O-heavy services
- Connection pooling — what it is, why it exists
- Docker networking — container DNS, why localhost doesn't work between containers
- Healthchecks and startup ordering in production
- Secrets management — never hardcode, inject via environment
- Migrations as code — Alembic, why they run in the container
- Event-driven architecture — Kafka as buffer, decoupling producers from consumers
- Redis as derived cache — source of truth vs derived state
- lifespan pattern — startup/shutdown resource management in FastAPI
- `async with` — context managers for guaranteed cleanup and leak prevention
