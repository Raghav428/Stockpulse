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
        return int(payload["sub"])
    except JWTError:
        raise ValueError("Invalid token")
