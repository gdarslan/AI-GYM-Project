from app.security import hash_password, password_problem, token_hash, verify_password


def test_hash_and_verify():
    stored = hash_password("correct horse battery")
    assert verify_password("correct horse battery", stored)
    assert not verify_password("correct horse batterY", stored)
    assert "correct horse battery" not in stored


def test_same_password_gets_a_different_hash_each_time():
    assert hash_password("same password") != hash_password("same password")     # random salt


def test_malformed_hash_is_rejected():
    assert not verify_password("anything", "not-a-hash")
    assert not verify_password("anything", "md5$1$abc$def")


def test_password_rules():
    assert password_problem("short") is not None
    assert password_problem("x" * 129) is not None
    assert password_problem("Password1") is not None                 # common, any case
    assert password_problem("alice2026!", username="alice") is not None
    assert password_problem("correct horse battery", username="alice") is None


def test_token_hash_is_stable_and_not_the_token():
    assert token_hash("abc") == token_hash("abc") != "abc"
