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
├── .env                            # POSTGRES_PASSWORD, SECRET_KEY (gitignored)
├── .gitignore                      # Ignores __pycache__, .venv, .env, setup_manual.txt
├── .python-version                 # Python 3.12
├── .vscode/
│   └── settings.json               # IDE config to hide __pycache__, .pyc, .pyo etc
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI entry point (lifespan, async sessions, routers)
│   ├── api/
│   │   └── register.py             # Auth endpoints (register, login, user details)
│   ├── core/
│   │   ├── auth.py                 # Protected routes (get_current_user, OAuth2)
│   │   ├── crypto.py               # Passwords/JWT (argon2, PyJWT)
│   │   └── database.py             # Async engine, session factory, Base, URLs
│   ├── crud/                       # Future DB query functions (empty)
│   ├── models/
│   │   └── models.py               # SQLAlchemy User model (id, email, DOB, etc)
│   └── schemas/
│       └── schema.py               # Pydantic validation schemas (Stock, UserCreate, Login)
├── migrations/
│   ├── env.py                      # Uses ALEMBIC_DATABASE_URL + Base metadata + models import
│   └── versions/
│       ├── d6f77d76792d_create_users_table.py
│       ├── fd2b8035fbf9_description_of_change.py
│       ├── 954652c52dec_enhanced_user_details.py
│       ├── 4c7e3028161a_updated_database.py
│       └── c1ab01ca91e9_watchlist_tables.py
├── Dockerfile                      # python:3.12-slim, uv, start.sh entrypoint
├── compose.yml                     # PostgreSQL + Redis + FastAPI
├── start.sh                        # Runs alembic upgrade head then uvicorn
├── alembic.ini
├── setup_manual.txt                # Developer notes for Docker commands
├── project_overview.txt            # Repository overview
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
- The `SECRET_KEY` environment variable is required by `app/core/crypto.py` but is currently missing from `.env` and `compose.yml`. This will crash login endpoints on token creation.

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
from fastapi import FastAPI
from app.core.database import engine
from contextlib import asynccontextmanager
from app.api.register import router as auth_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
app.include_router(auth_router)
```

**`app/models/models.py`**
```python
from app.core.database import Base
from sqlalchemy import Column, String, Integer, DateTime, Date, Boolean, ForeignKey, UniqueConstraint
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

class Watchlist(Base):
    __tablename__ = "Watchlists"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("Users.id"), nullable=False)
    
class WatchlistItem(Base):
    __tablename__ = "WatchlistItems"
    
    id = Column(Integer, primary_key=True)
    watchlist_id = Column(Integer, ForeignKey("Watchlists.id"), nullable=False)
    symbol = Column(String, nullable=False)
    
    __table_args__ = (
        UniqueConstraint("watchlist_id", "symbol", name="uq_watchlist_item"),
    )
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

**`app/schemas/schema.py`**
```python
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from datetime import date, datetime

class Stock(BaseModel):
    symbol : str = Field(min_length=1, max_length=5)

class UserCreate(BaseModel):
    first_name : str = Field(min_length=1, max_length=50)
    last_name : str
    DOB : date
    email : EmailStr
    password : str = Field(min_length=8)

class UserResponse(BaseModel):
    id : int
    is_active: bool
    created_at : datetime
    first_name : str
    last_name : str
    email: EmailStr
    DOB : date
    model_config = ConfigDict(from_attributes = True)

class UserLogin(BaseModel):
    email : EmailStr
    password : str
```

**`app/core/crypto.py`**
```python
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash, VerificationError
from datetime import datetime, timedelta, timezone
from jwt import encode, decode
from jwt.exceptions import PyJWTError as JWTError
import os

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is not set")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRY_IN_HOURS = 12

ph = PasswordHasher(
    time_cost=3, memory_cost=102400, parallelism=8,
    hash_len=32, salt_len=16
)

def _normalize(password: str) -> str:
    return password.strip()

def hash_password(password: str) -> str:
    password = _normalize(password)
    return ph.hash(password)

def verify_password(plain_password: str, password_hash: str) -> tuple[bool, str | None]:
    try:
        plain_password = _normalize(plain_password)
        ph.verify(password_hash, plain_password)
        if ph.check_needs_rehash(password_hash):
            return True, ph.hash(plain_password)
        return True, None
    except VerifyMismatchError:
        return False, None
    except (InvalidHash, VerificationError):
        return False, None

def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id), "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=ACCESS_TOKEN_EXPIRY_IN_HOURS)).timestamp()),
    }
    return encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token:str) -> int:
    try:
        payload = decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except JWTError:
        raise ValueError("Invalid token")
```

**`app/core/auth.py`**
```python
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from datetime import datetime, timezone
from app.core.crypto import decode_access_token
from app.core.database import get_db
from app.models.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    try:
        user_id = decode_access_token(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Credentials")
    
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Credentials")
    return user
```

**`app/api/register.py`**
```python
from fastapi import APIRouter, HTTPException, status
from app.schemas.schema import UserCreate, UserResponse, UserLogin
from app.models.models import User
from sqlalchemy import select
from app.core.database import get_db
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.crypto import hash_password, verify_password, create_access_token
from app.core.auth import get_current_user


router = APIRouter(prefix = '/api/v1/auth')
@router.post("/register")
async def register_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    existing =  ( await db.execute(select(User).where(User.email == user_data.email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Registration failed!")

    hashed_password = hash_password(user_data.password) 
    user = User(
        email = user_data.email,
        hashed_password = hashed_password,
        is_active = True,
        DOB = user_data.DOB,
        first_name = user_data.first_name,
        last_name = user_data.last_name
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)

@router.get("/users/me")
async def get_user_data(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)

@router.get("/users/{id}")
async def fetch_user(id: int, db: AsyncSession = Depends(get_db)):
    user =  ( await db.execute(select(User).where(User.id == id))).scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found")        
    return UserResponse.model_validate(user)

@router.post("/login")
async def login(user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    existing =  ( await db.execute(select(User).where(User.email == user_data.email))).scalar_one_or_none()

    if not existing:
        raise HTTPException(status_code=401, detail="Invalid Credentials")

    is_valid, new_hash = verify_password(user_data.password, existing.hashed_password)
    if is_valid:
        if new_hash:
            existing.hashed_password = new_hash
            await db.commit()
            await db.refresh(existing)
        token = create_access_token(existing.id)
        return {"token":str(token), "token_type": "bearer"}
    else:
        raise HTTPException(status_code=401, detail="Invalid Credentials")
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
- [x] `POST /api/v1/auth/login` — verify credentials, return JWT token
- [x] Understand JWT structure: header, payload, signature

### Day 4 — Protected Routes + Middleware
- [x] Decode and verify JWT on protected routes
- [x] Build a `get_current_user` dependency
- [x] `GET /users/me` — returns current user from token
- [x] Understand FastAPI middleware vs dependencies

### Day 5 — Watchlist Model + CRUD
- [x] Design `Watchlist` and `WatchlistItem` models
- [x] Migrations for new tables
- [ ] `POST /watchlists`, `GET /watchlists`, `POST /watchlists/{id}/stocks`, `DELETE`
- [x] Foreign keys and relationships in SQLAlchemy

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
