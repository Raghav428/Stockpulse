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