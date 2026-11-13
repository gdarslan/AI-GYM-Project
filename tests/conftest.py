import pytest

from app import security


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch):
    """600,000 PBKDF2 rounds take ~0.5 s per hash: fine for a login, too slow for a test suite."""
    monkeypatch.setattr(security, "ITERATIONS", 1_000)
