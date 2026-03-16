"""Unit tests for API key generation and hashing."""

from taskmeagents.auth.api_key import generate_api_key, hash_api_key


def test_generate_api_key_format():
    key = generate_api_key()
    assert key.startswith("tma_")
    assert len(key) > 40


def test_generate_api_key_uniqueness():
    keys = {generate_api_key() for _ in range(100)}
    assert len(keys) == 100


def test_hash_api_key_deterministic():
    key = "tma_test123"
    assert hash_api_key(key) == hash_api_key(key)


def test_hash_api_key_different_keys():
    assert hash_api_key("tma_aaa") != hash_api_key("tma_bbb")


def test_hash_api_key_sha256():
    h = hash_api_key("tma_test")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)
