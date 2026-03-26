from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash, VerificationError


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
