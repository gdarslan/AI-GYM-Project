"""Password hashing, password rules and session tokens. Standard library only.

Passwords: PBKDF2-HMAC-SHA256 with a random 16-byte salt and 600,000 iterations (OWASP recommendation).
Only the hash is stored; the password itself can never be read back.
Session tokens: random, sent to the browser once; the database stores only their SHA-256 hash, so a leaked
database does not give access to anyone's session.
"""
import base64
import hashlib
import hmac
import secrets

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600_000
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
COMMON_PASSWORDS = {"password", "password1", "12345678", "123456789", "1234567890", "qwerty123", "iloveyou",
                    "11111111", "00000000", "abc12345", "welcome1", "letmein1", "football", "baseball",
                    "sunshine", "princess", "admin123", "passw0rd", "qwertyuiop", "gymgymgym"}


def hash_password(password: str, iterations: int | None = None) -> str:
    iterations = iterations or ITERATIONS      # read at call time, so tests can lower it for speed
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"{ALGORITHM}${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, digest = stored.split("$")
    except ValueError:
        return False
    if algorithm != ALGORITHM:
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt), int(iterations))
    return hmac.compare_digest(check, base64.b64decode(digest))      # constant time: no timing leaks


# Verifying against this when a username does not exist makes a wrong username take as long as a wrong
# password, so response times do not reveal which usernames exist.
DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def password_problem(password: str, username: str = "") -> str | None:
    """Why a new password is not allowed, or None if it is fine (NIST-style: length + not a known password)."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Password must be at most {MAX_PASSWORD_LENGTH} characters."
    if password.lower() in COMMON_PASSWORDS:
        return "This password is too common. Choose another one."
    if username and username.lower() in password.lower():
        return "Password must not contain your username."
    return None


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
