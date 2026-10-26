"""Unit-bank fixtures own their contents; product bootstrap has a separate test.

Tests that exercise the shipped core set opt in explicitly through Settings.
No network model keys or production database are used by these fixtures.
"""
import pytest

@pytest.fixture(autouse=True)
def isolate_optional_shipped_bank(monkeypatch):
    monkeypatch.setenv('DIAGNOSTIC_CORE_ENABLED','false')
