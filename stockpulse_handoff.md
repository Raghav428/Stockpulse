# StockPulse AI — Project Handoff Document v4
**Last Updated:** April 7, 2026
**Purpose:** Complete context for any engineer, mentor, or LLM continuing this project

---

## 1. WHO IS THE LEARNER?

- Decent Python knowledge (sync FastAPI, uv package manager, basic PostgreSQL/SQL)
- Comfortable with Linux CLI (navigate, edit files, processes)
- Has used docker-compose before, heard of Kubernetes but never used it
- 4+ hrs/day available
- Goal: Proficiency + interview-level clarity across Full-Stack, Distributed Systems, and MLOps in 6 weeks
- Preferred style: **Socratic/guided** — ask questions, let the learner reason to answers before giving them. Only explain directly when they say "no idea" twice or the concept is not guessable.

---

## 2. THE PROJECT: StockPulse AI Platform

A real-time stock data ingestion, storage, querying, and AI-driven analysis platform. It streams live financial data, predicts short-term movements, and generates human-readable market narratives using LLMs.

### Why this project justifies the stack:
| Technology | Justification |
|---|---|
| Cassandra | Time-series tick data — write-heavy, append-only, massive volume |
| PostgreSQL | User accounts, watchlists, alert configs — relational, ACID |
| Redis | Live intraday cache & Pub/Sub for WebSockets |
| Kafka | Event buffer between ingestion, storage, and AI inference |
| FastAPI (async) | I/O-heavy service — async prevents event loop blocking |
| PyTorch / LSTM | Time-Series Engine — predicts next-n ticks based on historical windows |
| Ollama / LangChain | Narrative Agent — runs a quantized LLM locally to explain price action |
| Docker / K8s | Orchestration of 10 independent microservices at scale |
| GitHub Actions | CI/CD — push → test → build → deploy |
| AWS | Cloud runtime environment |

---

## 3. ARCHITECTURE (DESIGNED FROM FIRST PRINCIPLES)

```text
Browser (React/Grafana Dashboard)
  → nginx (SSL termination, reverse proxy, load balancing)
    → FastAPI service (async, handles HTTP + WebSocket)
      → Redis (live intraday data, derived cache)
      → Cassandra (historical tick data)
      → PostgreSQL (users, watchlists, alerts)

Ingestion & AI Pipeline (Event-Driven):
  External API (Yahoo/NSE/BSE)
    → Ingestion Service
      → Kafka (`ticks` topic)
        ├── Consumer Service (writes to Redis + Cassandra)
        ├── AI Prediction Service (reads `ticks`, infers future price, writes to `predictions` topic)
        └── AI Narrative Service (reads `ticks` + `predictions`, generates summary, writes to Redis)
```

### Key architectural decisions made:
- **Cassandra schema:** `PRIMARY KEY ((symbol, date), ts)` — partition by symbol+date, cluster by timestamp. Prevents unbounded partition growth, enables fast range queries.
- **Redis is stateless** — derived from Kafka, no volume needed. Kafka can rebuild it after restart.
- **Event-driven notifications** — ticks fire events, alert consumers react. No polling.
- **10 independent services:** PostgreSQL, Cassandra, Redis, Kafka, FastAPI, Consumer Service, Ingestion Service, nginx, AI Prediction Service, AI Narrative Service

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
├── .env.example                    # Template for .env
├── .gitignore
├── .python-version                 # Python 3.12
├── .dockerignore
├── .vscode/
│   └── settings.json
├── .env.example
├── nginx.conf
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI entry point (lifespan, routers)
│   ├── api/
│   │   ├── register.py             # Auth endpoints (register, login, users/me, users/{id})
│   │   └── watchlists.py           # Watchlist CRUD endpoints
│   ├── core/
│   │   ├── auth.py                 # get_current_user dependency (OAuth2 + JWT decode)
│   │   ├── crypto.py               # Argon2 hashing + PyJWT token create/decode
│   │   └── database.py             # Async engine, session factory, Base, URLs, get_db
│   ├── crud/                       # Empty — future DB query functions
│   ├── models/
│   │   └── models.py               # SQLAlchemy: User, Watchlist, WatchlistItem
│   └── schemas/
│       └── schema.py               # Pydantic: Stock, UserCreate, UserResponse, UserLogin,
│                                   #           WatchlistCreate, AppendWatchlist, WatchlistResponse
├── migrations/
│   ├── env.py
│   └── versions/
│       ├── d6f77d76792d_create_users_table.py
│       ├── fd2b8035fbf9_add_hashed_password.py
│       ├── 954652c52dec_enhanced_user_details.py
│       ├── 4c7e3028161a_updated_database.py
│       └── c1ab01ca91e9_watchlist_tables.py
├── Dockerfile
├── compose.yml
├── start.sh
├── alembic.ini
├── pyproject.toml
├── uv.lock
├── README.md
└── setup_manual.txt
```

### What is fully working:
- Full Docker Compose stack: PostgreSQL + Redis + FastAPI boots cleanly from scratch
- PostgreSQL healthcheck — FastAPI waits for `service_healthy` before starting
- `start.sh` entrypoint — Alembic migrations run automatically on every container start
- `.env` secrets — `POSTGRES_PASSWORD` and `SECRET_KEY` injected via Compose, gitignored
- FastAPI `/health` — runs real `SELECT 1` against PostgreSQL via async session
- `Depends(get_db)` — async session injected into routes, guaranteed cleanup via `async with`
- `POST /api/v1/auth/register` — validates, checks duplicate email, hashes password (Argon2), writes to DB
- `POST /api/v1/auth/login` — verifies credentials, opportunistic rehash, returns `{"token": ..., "token_type": "bearer"}`
- `GET /api/v1/auth/users/me` — protected route, returns current user from JWT
- `GET /api/v1/auth/users/{id}` — fetch user by ID, 404 if not found or inactive
- `get_current_user` dependency — extracts Bearer token, decodes JWT, fetches User from DB
- `POST /api/v1/watchlists` — creates watchlist for authenticated user
- `GET /api/v1/watchlists` — returns all watchlists for current user with symbols (via selectinload)
- `POST /api/v1/watchlists/{id}/stocks` — adds stock to watchlist, 409 on duplicate
- `DELETE /api/v1/watchlists/{id}/stocks/{symbol}` — removes stock from watchlist
- Alembic migrations — full schema history, runs automatically in container on startup
- Async SQLAlchemy with `asyncpg` — connection pooling via `async_sessionmaker`
- Layer caching in Docker builds — dependencies cached separately from code
- Volume persistence — `pgdata` survives container restarts
- Bind mount with `.venv` exclusion — local code changes reflect in container without rebuilds

### ⚠️ Known issues / pending:
- `pydantic-settings` and `structlog` installed but not yet wired in
- Login returns `{"token": ..., "token_type": "bearer"}` — note the key is `token` not `access_token`. Non-standard but functional. Consider aligning with OAuth2 spec (`access_token`) later.
- `selectinload` vs JOIN — learner understands what selectinload does but hasn't fully articulated why it's better than a JOIN for N+1 scenarios. Pending discussion.

---

## 5. KEY FILES (CURRENT EXACT STATE)

**`app/main.py`**
```python
from fastapi import FastAPI
from app.core.database import engine
from contextlib import asynccontextmanager
from app.api.register import router as auth_router
from app.api.watchlists import router as watchlists_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
app.include_router(auth_router)
app.include_router(watchlists_router)
```

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

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
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
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=ACCESS_TOKEN_EXPIRY_IN_HOURS)).timestamp()),
    }
    return encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> int:
    try:
        payload = decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload.get("sub"))
    except JWTError:
        raise ValueError("Invalid token")
```

**`app/core/auth.py`**
```python
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
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

**`app/models/models.py`**
```python
from app.core.database import Base
from sqlalchemy import Column, String, Integer, DateTime, Date, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
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
    items = relationship("WatchlistItem", back_populates="watchlist")

class WatchlistItem(Base):
    __tablename__ = "WatchlistItems"
    id = Column(Integer, primary_key=True)
    watchlist_id = Column(Integer, ForeignKey("Watchlists.id"), nullable=False)
    symbol = Column(String, nullable=False)
    watchlist = relationship("Watchlist", back_populates="items")
    __table_args__ = (
        UniqueConstraint("watchlist_id", "symbol", name="uq_watchlist_item"),
    )
```

**`app/schemas/schema.py`**
```python
from pydantic import BaseModel, Field, EmailStr, ConfigDict, model_validator
from datetime import date, datetime

class Stock(BaseModel):
    symbol: str = Field(min_length=1, max_length=5)

class UserCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str
    DOB: date
    email: EmailStr
    password: str = Field(min_length=8)

class UserResponse(BaseModel):
    id: int
    is_active: bool
    created_at: datetime
    first_name: str
    last_name: str
    email: EmailStr
    DOB: date
    model_config = ConfigDict(from_attributes=True)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)

class AppendWatchlist(BaseModel):
    symbol: str = Field(min_length=1, max_length=5)

class WatchlistResponse(BaseModel):
    id: int
    name: str
    user_id: int
    symbols: list[str] = []
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode='before')
    @classmethod
    def extract_symbols(cls, data):
        if hasattr(data, 'items'):
            data.__dict__['symbols'] = [item.symbol for item in data.items]
        return data
```

**`app/api/register.py`**
```python
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import OAuth2PasswordRequestForm

from app.schemas.schema import UserCreate, UserResponse, UserLogin
from app.models.models import User
from app.core.database import get_db
from app.core.crypto import hash_password, verify_password, create_access_token
from app.core.auth import get_current_user

router = APIRouter(prefix='/api/v1/auth')

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = (await db.execute(select(User).where(User.email == user_data.email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Registration failed!")

    user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        is_active=True,
        DOB=user_data.DOB,
        first_name=user_data.first_name,
        last_name=user_data.last_name
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)

@router.get("/users/me", response_model=UserResponse)
async def get_user_data(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)

@router.get("/users/{id}", response_model=UserResponse)
async def fetch_user(id: int, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.id == id))).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found")
    return UserResponse.model_validate(user)

@router.post("/login")
async def login(user_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    existing = (await db.execute(select(User).where(User.email == user_data.username))).scalar_one_or_none()
    if not existing:
        raise HTTPException(status_code=401, detail="Invalid Credentials")

    is_valid, new_hash = verify_password(user_data.password, existing.hashed_password)
    if is_valid:
        if new_hash:
            existing.hashed_password = new_hash
            await db.commit()
            await db.refresh(existing)
        token = create_access_token(existing.id)
        return {"token": str(token), "token_type": "bearer"}
    else:
        raise HTTPException(status_code=401, detail="Invalid Credentials")
```

**`app/api/watchlists.py`**
```python
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.models import User, Watchlist, WatchlistItem
from app.schemas.schema import WatchlistCreate, AppendWatchlist, WatchlistResponse

router = APIRouter(prefix='/api/v1/watchlists')

@router.post("", status_code=status.HTTP_201_CREATED, response_model=WatchlistResponse)
async def create_watchlist(data: WatchlistCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    watchlist = Watchlist(name=data.name, user_id=user.id)
    db.add(watchlist)
    await db.commit()
    await db.refresh(watchlist)
    result = await db.execute(
        select(Watchlist).where(Watchlist.id == watchlist.id).options(selectinload(Watchlist.items))
    )
    return WatchlistResponse.model_validate(result.scalar_one())

@router.get("", response_model=list[WatchlistResponse])
async def get_watchlists(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Watchlist).where(Watchlist.user_id == user.id).options(selectinload(Watchlist.items))
    )
    return [WatchlistResponse.model_validate(wl) for wl in result.scalars().all()]

@router.post("/{id}/stocks", status_code=status.HTTP_201_CREATED)
async def add_stock(id: int, data: AppendWatchlist, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    watchlist = (await db.execute(select(Watchlist).where(Watchlist.id == id, Watchlist.user_id == user.id))).scalar_one_or_none()
    if not watchlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist not found")

    existing = (await db.execute(
        select(WatchlistItem).where(WatchlistItem.watchlist_id == id, WatchlistItem.symbol == data.symbol.upper())
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{data.symbol.upper()} is already in this watchlist")

    db.add(WatchlistItem(watchlist_id=id, symbol=data.symbol.upper()))
    await db.commit()
    return {"detail": f"{data.symbol.upper()} added to watchlist '{watchlist.name}'"}

@router.delete("/{id}/stocks/{symbol}", status_code=status.HTTP_200_OK)
async def remove_stock(id: int, symbol: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    watchlist = (await db.execute(select(Watchlist).where(Watchlist.id == id, Watchlist.user_id == user.id))).scalar_one_or_none()
    if not watchlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist not found")

    item = (await db.execute(
        select(WatchlistItem).where(WatchlistItem.watchlist_id == id, WatchlistItem.symbol == symbol.upper())
    )).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{symbol.upper()} not found in this watchlist")

    await db.delete(item)
    await db.commit()
    return {"detail": f"{symbol.upper()} removed from watchlist '{watchlist.name}'"}
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
      SECRET_KEY: ${SECRET_KEY}
    volumes:
      - .:/app
      - /app/.venv
    ports:
      - "8000:8000"
    depends_on:
      my_postgres:
        condition: service_healthy
    healthcheck:
      test: ['CMD-SHELL', 'curl -f http://localhost:8000/health']
      interval: 5s
      timeout: 5s
      retries: 5

  nginx:
    image: nginx
    volumes:
    - ./nginx.conf:/etc/nginx/nginx.conf
    ports:
    - "80:80"
    depends_on:
      fastapi:
        condition: service_healthy

volumes:
  pgdata:
```

**`nginx.conf`**
```nginx
server {
    listen 80;
    location / {
        proxy_pass http://fastapi:8000;
    }
}
```

**`.env.example`**
```text
POSTGRES_PASSWORD=...................
SECRET_KEY=................
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

**`start.sh`**
```bash
#!/bin/bash
uv run alembic upgrade head
/app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Dependencies (`pyproject.toml`):
```
alembic, argon2-cffi, asyncpg, cryptography, dotenv, fastapi, numpy, pandas,
psycopg2-binary, pydantic-settings, pydantic[email], pyjwt, python-dotenv,
python-multipart, sqlalchemy, starlette, structlog, uvicorn
```

---

## 6. CONCEPTS THE LEARNER HAS DEEPLY UNDERSTOOD

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
- **Depends pattern:** dependency injection, `get_db`, session lifecycle managed by FastAPI
- **SQLAlchemy models vs Pydantic schemas:** DB layer vs API layer, why you never return a model directly
- **Argon2 hashing:** salting, why deliberate slowness matters, time/memory/parallelism cost parameters, opportunistic rehashing
- **JWT structure:** header, payload (sub/iat/exp), signature — why the signature makes tokens trustworthy
- **Bearer token auth:** Authorization header, OAuth2PasswordBearer, get_current_user dependency
- **Route ordering:** why `/users/me` must be defined before `/users/{id}` in FastAPI
- **SQLAlchemy relationships:** `relationship()`, `back_populates`, one-to-many, many-to-many via junction table
- **selectinload:** fires one query per relationship level instead of N queries, avoids N+1 problem
- **model_validator:** pre-validation transformation in Pydantic, used to extract symbols from WatchlistItems
- **from_attributes:** allows Pydantic to read SQLAlchemy objects directly
- **db.refresh():** re-syncs in-memory object with DB after commit so server-set fields (id, created_at) are populated

---

## 7. TEACHING STYLE NOTES

- **Socratic first** — always ask the learner to reason before explaining
- **Build on prior reasoning** — reference things the learner already said/figured out
- **One concept at a time** — learner explicitly said "you're telling me to do too much at once"
- **Concrete over abstract** — analogies (hospital receptionist for nginx, library for connection pool) land well
- **Let them fail and debug** — the `inr` typo, the 500 error, the `engine=` keyword bug, the `/users/me` route ordering bug were all valuable learning moments
- **Don't give code until they've attempted it** — show skeleton, ask them to fill gaps
- **When they say "no idea" twice** — just explain directly, don't keep probing
- **They pull from previous projects** — don't dismiss it, but make sure they understand the code they're using (e.g. crypto.py, watchlists.py)

---

## 8. 20-DAY PLAN (Day-by-Day)

### Day 1 ✅
- [x] `async with` deep dive — context managers, guaranteed cleanup
- [x] Generate missing Alembic migration for User model updates
- [x] Introduce `Depends` pattern for DB sessions

### Day 2 ✅ — User CRUD + Pydantic Schemas
- [x] Create `UserCreate` and `UserResponse` Pydantic schemas
- [x] `POST /api/v1/auth/register` — create a user, write to PostgreSQL
- [x] `GET /api/v1/auth/users/{id}` — fetch user by ID
- [x] Understand SQLAlchemy models (DB layer) vs Pydantic schemas (API layer)
- [x] Understand why you never return a SQLAlchemy model directly from a route

### Day 3 ✅ — Password Hashing + Auth Setup
- [x] Hash passwords with `argon2-cffi` before storing
- [x] JWT token generation + decode functions
- [x] `POST /api/v1/auth/login` — verify credentials, opportunistic rehash, return JWT
- [x] Understand JWT structure: header, payload, signature

### Day 4 ✅ — Protected Routes
- [x] `get_current_user` dependency — OAuth2PasswordBearer + JWT decode + DB lookup
- [x] `GET /api/v1/auth/users/me` — returns current user from token
- [x] Route ordering fix — `/users/me` before `/users/{id}`
- [x] Testing protected routes with curl + Bearer token

### Day 5 ✅ — Watchlist Model + CRUD
- [x] Designed Watchlist + WatchlistItem models (many-to-many via junction table)
- [x] Migrations for new tables
- [x] `relationship()` + `back_populates` + `selectinload`
- [x] `model_validator` to extract symbols from WatchlistItems into WatchlistResponse
- [x] `POST /watchlists`, `GET /watchlists`, `POST /watchlists/{id}/stocks`, `DELETE /watchlists/{id}/stocks/{symbol}`

### Day 6 🚧 — nginx
- [ ] Add nginx container to compose
- [ ] Write `nginx.conf` — reverse proxy to FastAPI
- [ ] Understand `location` blocks, `proxy_pass`, `upstream`
- [ ] All traffic flows through nginx, not directly to FastAPI
- [ ] Test all existing endpoints work through nginx

### Day 7 — Review + Git + README
- [ ] Set up proper Git repo with meaningful commit history
- [ ] Write README with ASCII architecture diagram
- [ ] Full `docker compose down -v && docker compose up --build` from scratch — verify clean boot

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

## 9. INTERVIEW TALKING POINTS ALREADY EARNED

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
- `Depends` pattern — dependency injection in FastAPI, session lifecycle
- SQLAlchemy models vs Pydantic schemas — why the separation exists
- Argon2 vs bcrypt — memory-hard hashing, why cost parameters matter
- JWT — header/payload/signature, why you don't store tokens server-side
- OAuth2 Bearer tokens — how the Authorization header works
- Many-to-many relationships — junction tables, why JSON blobs are the wrong answer
- selectinload vs JOIN — N+1 problem, one query per level vs cross-product rows
- `db.refresh()` — why you need it after commit, what SQLAlchemy expiry means
