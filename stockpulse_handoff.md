    # StockPulse AI — Project Handoff Document v5
    **Last Updated:** April 10, 2026
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

    Ingestion & AI Pipeline (Design Intent — 🏗️ Partially Implemented):
    External API (Binance WebSocket — *Current Implementation*)
        → Ingestion Service (🏗️ Active)
        → Kafka (`ticks` topic — 🏗️ Active)
            ├── Consumer Service (⏳ PLANNED — writes to Redis + Cassandra)
            ├── AI Prediction Service (⏳ PLANNED — reads `ticks`, infers future price)
            └── AI Narrative Service (⏳ PLANNED — generates summary)
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
    ├── nginx.conf                  # Basic reverse proxy configuration
    ├── ingestion/                  # Ingestion Service (Binance WebSocket)
    │   ├── ingestion.py            # Kafka producer logic
    │   ├── Dockerfile              # uv-based container build
    │   └── pyproject.toml          # Service-specific dependencies
    ├── app/
    │   ├── __init__.py
    │   ├── main.py                 # FastAPI entry point (lifespan, routers)
    │   ├── api/
    │   │   ├── register.py         # Auth endpoints
    │   │   ├── watchlists.py       # Watchlist CRUD
    │   │   └── historical_data.py  # Cassandra fetch logic
    │   ├── core/
    │   │   ├── auth.py             # get_current_user dependency
    │   │   ├── crypto.py           # Argon2 + JWT logic
    │   │   ├── postgresql.py       # Async PG engine/session
    │   │   └── cassandra.py        # Cassandra cluster/session
    │   ├── crud/                   # Empty — future DB query functions
    │   ├── models/
    │   │   └── models.py           # SQLAlchemy models
    │   └── schemas/
    │       └── schema.py           # Pydantic schemas
    ├── migrations/
    │   ├── env.py
    │   └── versions/
    │       └── ...                 # Migration history (5 files)
    ├── Dockerfile                  # Main FastAPI Dockerfile
    ├── compose.yml                 # Full stack orchestration
    ├── start.sh                    # Container entrypoint
    ├── alembic.ini
    ├── pyproject.toml
    ├── uv.lock
    ├── README.md
    ├── setup_manual.txt
    ├── test_producer.py            # Kafka test producer (OHLCV format)
    └── test_consumer.py            # Kafka test consumer (Print-only)
    ```

    ### What is fully working:
    - Full Docker Compose stack: PostgreSQL + Redis + Cassandra + FastAPI boots cleanly from scratch
    - Service healthchecks — FastAPI waits for PostgreSQL, Redis, and Cassandra to be `service_healthy` before starting
    - Improved reliability — Healthcheck retries increased to 50 to handle slow initial database boots
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
    - Volume persistence — `pgdata` (Postgres) and `cassandra_data` (Cassandra) survive container restarts
    - Bind mount with `.venv` exclusion — local code changes reflect in container without rebuilds
    - **Kafka local infrastructure** — Broker up and healthy in Compose
    - **Ingestion Service** — Working Binance WebSocket integration publishing to Kafka topic `ticks`
    - **Kafka connectivity verified** — `test_producer.py` and `test_consumer.py` flow working locally
    - **Historical data endpoints** — `GET /api/v1/historical_data/stocks/{symbol}/history` fetching from Cassandra
    - **nginx Reverse Proxy** — Basic routing to FastAPI functional
    - **Redis Infrastructure** — Service up and healthy (awaiting code integration)
    - **Dockerfile refinements** — `curl` installed for healthchecks

    ### ⚠️ Known issues / pending:
    - **Schema Mismatch:** `ingestion.py` produces raw trade data (`price`/`quantity`), but Cassandra and `test_producer.py` expect OHLCV format.
    - **Redis Wiring:** Redis is running but no application logic (Consumer or FastAPI) uses it yet.
    - **Documentation:** `README.md` refers to `project_overview.txt`, which is missing from the repo.
    - **Workspace Meta:** Root `pyproject.toml` has a duplicate `ingestion` member.
    - **Nginx:** Basic proxy only; lacks SSL and load balancing described in architecture.
    - `pydantic-settings` and `structlog` installed but not yet wired in
    - Login returns `{"token": ..., "token_type": "bearer"}` — note the key is `token` not `access_token`. Consider aligning with OAuth2 spec later.
    - `selectinload` vs JOIN — learner needs to articulate the N+1 reasoning more clearly.

    ---

    ## 5. KEY FILES (CURRENT EXACT STATE)

    **`app/main.py`**
    ```python
    from fastapi import FastAPI, Depends, status
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import select
    from app.core.postgresql import engine, get_db
    from app.core.cassandra import connect_cassandra, close_cassandra
    from contextlib import asynccontextmanager
    from app.api.register import router as auth_router
    from app.api.watchlists import router as watchlists_router
    from app.api.historical_data import router as historical_data_router


    @asynccontextmanager
    async def lifespan(app: FastAPI):
        connect_cassandra()
        yield
        await engine.dispose()
        close_cassandra()

    app = FastAPI(lifespan=lifespan)

    app.include_router(auth_router)
    app.include_router(watchlists_router)
    app.include_router(historical_data_router)


    @app.get("/health", status_code=status.HTTP_200_OK)
    async def health(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(1))
        
        if result:
            return {'status' : 'healthy'}
    ```

    **`app/core/postgresql.py`**
    ```python
    import os
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy.orm import declarative_base

    Base = declarative_base()

    ### PostgreSQL password loading
    pg_password = os.getenv("POSTGRES_PASSWORD")

    if pg_password:
        DATABASE_URL = f"postgresql+asyncpg://postgres:{pg_password}@my_postgres:5432/stockpulse"
    else:
        raise RuntimeError("POSTGRES_PASSWORD environment variable not set")
    ###

    #Sync Database URL for migrations
    ALEMBIC_DATABASE_URL = f"postgresql://postgres:{pg_password}@my_postgres:5432/stockpulse"   
    #Async engine
    engine = create_async_engine(DATABASE_URL)
    #Async session factory
    AsyncSessionLocal = async_sessionmaker(engine, class_= AsyncSession, expire_on_commit=False)



    async def get_db():
        async with AsyncSessionLocal() as session:
            yield session
    ```

    **`app/core/cassandra.py`**
    ```python
    from cassandra.cluster import Cluster

    cluster = None
    session = None

    def connect_cassandra():
        global cluster, session
        cluster = Cluster(["my_cassandra"])
        session = cluster.connect()

        session.execute("""
    CREATE KEYSPACE IF NOT EXISTS stockpulse
    WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1}
    """)
        session.set_keyspace("stockpulse")

        session.execute("""
        CREATE TABLE IF NOT EXISTS tick_data(
            symbol text,
            date text,
            ts timestamp,
            open double,
            high double,
            low double,
            close double,
            volume int,
            PRIMARY KEY ((symbol, date), ts)
        )""")

    def close_cassandra():
        cluster.shutdown()
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


    # Tuned for local dev / learning.
    # These parameters are SAFE and MEMORY-HARD.
    ph = PasswordHasher(
        time_cost=3,
        memory_cost=102400,  # 100 MB
        parallelism=8,
        hash_len=32,
        salt_len=16,
    )


    def _normalize(password: str) -> str:
        # Single normalization point
        return password.strip()


    def hash_password(password: str) -> str:
        password = _normalize(password)
        return ph.hash(password)

    def verify_password(plain_password: str, password_hash: str) -> tuple[bool, str | None]:
        try:
            plain_password = _normalize(plain_password)

            ph.verify(password_hash, plain_password)

            # Opportunistic rehash if parameters changed
            if ph.check_needs_rehash(password_hash):
                return True, ph.hash(plain_password)

            return True, None

        except VerifyMismatchError:
            # Wrong password
            return False, None

        except (InvalidHash, VerificationError):
            # Corrupt or legacy hash — treated as auth failure externally
            return False, None


    def create_access_token(user_id: int) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=ACCESS_TOKEN_EXPIRY_IN_HOURS)).timestamp()),
        }
        return encode(payload, SECRET_KEY, algorithm=ALGORITHM)


    def decode_access_token(token:str) -> int:
        try:
            payload = decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return int(payload.get("sub"))
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
    from app.core.crypto import decode_access_token
    from app.core.postgresql import get_db
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
    from app.core.postgresql import Base
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


    class WatchlistCreate(BaseModel):
        name : str = Field(min_length=1, max_length=50)
        

    class AppendWatchlist(BaseModel):
        symbol : str = Field(min_length=1, max_length=5)


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
        

    class StockHistory(BaseModel):
        date: date
        symbol: str
    ```

    **`app/api/register.py`**
    ```python
    from fastapi import APIRouter, HTTPException, status
    from app.schemas.schema import UserCreate, UserResponse
    from app.models.models import User
    from sqlalchemy import select
    from app.core.postgresql import get_db
    from fastapi import Depends
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.core.crypto import hash_password, verify_password, create_access_token
    from app.core.auth import get_current_user
    from fastapi.security import OAuth2PasswordRequestForm



    router = APIRouter(prefix = '/api/v1/auth')



    @router.post("/register", status_code=status.HTTP_201_CREATED)
    async def register_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    
        existing =  ( await
                db.execute(select(User)
                .where(User.email == user_data.email)
                )).scalar_one_or_none()

        
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Registration failed!"
            )

        hashed_password = hash_password(user_data.password) ###filler function

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


    @router.get("/users/me", response_model=UserResponse)
    async def get_user_data(user: User = Depends(get_current_user)):
        return UserResponse.model_validate(user)

        
    @router.get("/users/{id}", response_model=UserResponse)
    async def fetch_user(id: int, db: AsyncSession = Depends(get_db)):
    
        user =  ( await
                db.execute(select(User)
                .where(User.id == id)
                )).scalar_one_or_none()

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User Not Found"
            )        

        return UserResponse.model_validate(user)


    @router.post("/login")
    async def login(user_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):

        existing =  ( 
                await db.execute(select(User)
                .where(User.email == user_data.username)
                )).scalar_one_or_none()

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

    **`app/api/watchlists.py`**
    ```python
    from fastapi import APIRouter, HTTPException, Depends, status
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.core.postgresql import get_db
    from app.core.auth import get_current_user
    from app.models.models import User, Watchlist, WatchlistItem
    from app.schemas.schema import WatchlistCreate, AppendWatchlist, WatchlistResponse

    router = APIRouter(prefix='/api/v1/watchlists')


    @router.post("", status_code=status.HTTP_201_CREATED, response_model=WatchlistResponse)
    async def create_watchlist(
        data: WatchlistCreate,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """Create a new watchlist for the authenticated user."""
        watchlist = Watchlist(name=data.name, user_id=user.id)
        db.add(watchlist)
        await db.commit()
        await db.refresh(watchlist)

        # Re-fetch with items eagerly loaded so WatchlistResponse.symbols populates correctly
        result = await db.execute(
            select(Watchlist)
            .where(Watchlist.id == watchlist.id)
            .options(selectinload(Watchlist.items))
        )
        return WatchlistResponse.model_validate(result.scalar_one())


    @router.get("", response_model=list[WatchlistResponse])
    async def get_watchlists(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """Return all watchlists belonging to the authenticated user."""
        result = await db.execute(
            select(Watchlist)
            .where(Watchlist.user_id == user.id)
            .options(selectinload(Watchlist.items))
        )
        return [WatchlistResponse.model_validate(wl) for wl in result.scalars().all()]


    @router.post("/{id}/stocks", status_code=status.HTTP_201_CREATED)
    async def add_stock(
        id: int,
        data: AppendWatchlist,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """Add a stock symbol to an existing watchlist owned by the authenticated user."""
        result = await db.execute(
            select(Watchlist).where(Watchlist.id == id, Watchlist.user_id == user.id)
        )
        watchlist = result.scalar_one_or_none()

        if not watchlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Watchlist not found"
            )

        # Guard against duplicate symbols (db constraint will also catch this, but give a clean error)
        existing = await db.execute(
            select(WatchlistItem).where(
                WatchlistItem.watchlist_id == id,
                WatchlistItem.symbol == data.symbol.upper()
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{data.symbol.upper()} is already in this watchlist"
            )

        item = WatchlistItem(watchlist_id=id, symbol=data.symbol.upper())
        db.add(item)
        await db.commit()

        return {"detail": f"{data.symbol.upper()} added to watchlist '{watchlist.name}'"}


    @router.delete("/{id}/stocks/{symbol}", status_code=status.HTTP_200_OK)
    async def remove_stock(
        id: int,
        symbol: str,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """Remove a stock symbol from a watchlist owned by the authenticated user."""
        # Verify the watchlist belongs to this user
        result = await db.execute(
            select(Watchlist).where(Watchlist.id == id, Watchlist.user_id == user.id)
        )
        watchlist = result.scalar_one_or_none()

        if not watchlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Watchlist not found"
            )

        item_result = await db.execute(
            select(WatchlistItem).where(
                WatchlistItem.watchlist_id == id,
                WatchlistItem.symbol == symbol.upper()
            )
        )
        item = item_result.scalar_one_or_none()

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{symbol.upper()} not found in this watchlist"
            )

        await db.delete(item)
        await db.commit()

        return {"detail": f"{symbol.upper()} removed from watchlist '{watchlist.name}'"}

    **`app/api/historical_data.py`**
    ```python
    from fastapi import APIRouter, HTTPException, status
    from datetime import date as Date
    from typing import List, Dict
    from app.core.cassandra import session

    router = APIRouter(prefix = '/api/v1/historical_data')

    @router.get("/stocks/{symbol}/history")
    async def history(
        date: Date,
        symbol: str
    ) -> List[Dict]:
        """
        Fetch historical tick data from Cassandra for a specific symbol and date.
        """
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cassandra session not initialized"
            )

        # Note: date is converted to string for the CQL query as the schema uses 'text' for date
        data = session.execute(
            "SELECT * FROM tick_data WHERE symbol = %s AND date = %s",
            (symbol, str(date))
        )
        
        # Convert Cassandra row objects to dictionaries for JSON serialization
        results = [dict(row._asdict()) for row in data]
        
        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=f"No historical data found for {symbol} on {date}"
            )
            
        return results
    ```
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
        interval: 10s
        timeout: 5s
        retries: 50

    my_redis:
        image: redis
        ports:
        - "6379:6379"
        healthcheck:
        test: ['CMD-SHELL', 'redis-cli ping']
        interval: 10s
        timeout: 5s
        retries: 50

    my_cassandra:
        image: cassandra
        ports:
        - "9042:9042"
        volumes:
        - cassandra:/var/lib/cassandra
        healthcheck:
        test: ['CMD-SHELL', 'nodetool status']
        interval: 10s
        timeout: 5s
        retries: 50

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
        my_cassandra:
            condition: service_healthy
        my_redis:
            condition: service_healthy
        retries: 50
        healthcheck:
          test: ['CMD-SHELL', 'curl -f http://localhost:8000/health']
          interval: 10s
          timeout: 5s
          retries: 50

    ingestion:
        build:
            context: ./ingestion
            dockerfile: Dockerfile
        depends_on:
            kafka:
                condition: service_healthy

    nginx:
        image: nginx
        volumes:
        - ./nginx.conf:/etc/nginx/nginx.conf
        ports:
        - "80:80"
        depends_on:
        fastapi:
            condition: service_healthy

    kafka:
        image: confluentinc/cp-kafka:7.5.0
        ports:
        - "9092:9092"
        environment:
        KAFKA_NODE_ID: 1
        KAFKA_PROCESS_ROLES: broker,controller
        KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:29092,CONTROLLER://0.0.0.0:29093,PLAINTEXT_HOST://0.0.0.0:9092
        KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092
        KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
        KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:29093
        KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
        KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
        KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
        KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
        CLUSTER_ID: MkU3OEVBNTcwNTJENDM2Qk
        healthcheck:
        test: ["CMD-SHELL", "kafka-broker-api-versions --bootstrap-server localhost:9092"]
        interval: 10s
        timeout: 5s
        retries: 50

    volumes:
    pgdata:
    cassandra:
    ```

    **`nginx.conf`**
    ```nginx
    events{}

    http{
        server {
        listen 80;
        location / {
            proxy_pass http://fastapi:8000;
        }
    }
    }
    ```

    **`ingestion/ingestion.py`**
    ```python
    from kafka import KafkaProducer
    import json
    import websocket

    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    streams = ('@trade/'.join(symbols) + '@trade').lower()
    url = f"wss://stream.binance.com:9443/stream?streams={streams}"

    producer = KafkaProducer(
        bootstrap_servers='kafka:9092',
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

    def on_message(ws, message):
        data = json.loads(message)
        # Note: Producing raw price/quantity, creates schema drift with Cassandra OHLCV
        symbol, price, quantity, timestamp = data['data']['s'],data['data']['p'],data['data']['q'],data['data']['T']
        tick_data = {'symbol':symbol, 'price':price,'quantity':quantity,'timestamp':timestamp}
        producer.send('ticks',tick_data)

    ws = websocket.WebSocketApp(url,on_message=on_message)
    ws.run_forever()
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
    RUN apt-get update && apt-get install -y curl
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

    **`test_producer.py`**
    ```python
    from kafka import KafkaProducer
    import json, time

    producer = KafkaProducer(
        bootstrap_servers='localhost:9092',
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )


    for i in range(5):
        tick = {
            'symbol' : 'AAPL',
            'open' : 140 + i,
            'high' : 145 + i,
            'low' : 138 + i,
            'close' : 141 + i,
            'volume' : 100000 + 4057 * i,
            'timestamp' : time.time()
        }

        producer.send(
            topic = 'ticks',
            key = tick['symbol'].encode('utf-8'),
            value=tick
        )

        print(f"Sent: {tick}")
        time.sleep(1)


    producer.flush()
    producer.close()
    ```

    **`test_consumer.py`**
    ```python
    from kafka import KafkaConsumer
    import json

    consumer = KafkaConsumer(
        'ticks',
        bootstrap_servers='localhost:9092',
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        auto_offset_reset='earliest',
        group_id='test-group'
    )

    print("Listening for messages...")
    for message in consumer:
        print(f"Received: {message}")
    ```

    ### Dependencies (`pyproject.toml`):
    ```
    alembic, argon2-cffi, asyncpg, cassandra-driver, cryptography, dotenv, fastapi, 
    kafka-python-ng, numpy, pandas, psycopg2-binary, pydantic-settings, pydantic[email], 
    pyjwt, python-dotenv, python-multipart, sqlalchemy, starlette, structlog, uvicorn,
    websocket-client
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

    ### Day 6 ✅ — nginx
    - [x] Add nginx container to compose
    - [x] Write `nginx.conf` — reverse proxy to FastAPI
    - [x] Understand `location` blocks, `proxy_pass`, `upstream`
    - [x] All traffic flows through nginx (FastAPI port 8000 remains exposed for direct access/debugging)
    - [x] Test all existing endpoints work through nginx

    ### Day 7 ✅ — Review + Git + README
    - [x] Set up proper Git repo with meaningful commit history
    - [x] Write README with ASCII architecture diagram
    - [x] Full `docker compose down -v && docker compose up --build` from scratch — verify clean boot

    ### Day 8 ✅ — Cassandra Introduction
    - [x] Add Cassandra to compose
    - [x] Understand keyspaces, tables, partitions
    - [x] Connect from Python using `cassandra-driver`
    - [x] Create `tick_data` table: `PRIMARY KEY ((symbol, date), ts)`
    - [x] Insert and query dummy tick rows

    ### Day 9 ✅ — Cassandra + FastAPI Integration
    - [x] `GET /stocks/{symbol}/history?date=2026-03-25`
    - [x] Query Cassandra for tick data by symbol + date
    - [x] Handle "no data found" gracefully

    ### Day 10  — Kafka Introduction ✅
    - [x] Add Kafka to compose
    - [x] Understand topics, partitions, producers, consumers, consumer groups
    - [x] Write a minimal producer and consumer in Python
    - [x] Verify end-to-end message flow

    ### Day 11 — Ingestion Service
    -  Build `ingestion/` as a separate Python service
    -  Fetch real trade data from Binance WebSocket (Crypto)
    -  Publish each trade as JSON to Kafka topic `ticks`
    -  Containerize and add to compose

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
